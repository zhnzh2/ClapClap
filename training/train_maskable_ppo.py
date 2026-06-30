"""Offline training entrypoint for ClapClap 1.0 AI.

The production web app must not import or run this module. It is intentionally
kept under training/ and only imports heavyweight RL dependencies when a real
training run is requested.

Usage
-----
  # 查看所有参数
  python training/train_maskable_ppo.py --help

  # Dry-run: 只验证 manifest，不训练
  python training/train_maskable_ppo.py --dry-run

  # Smoke test: 最小训练验证全链路
  python training/train_maskable_ppo.py --smoke-test

  # 真实训练（推荐起步命令）
  python training/train_maskable_ppo.py \\
      --total-timesteps 500000 \\
      --model-version v0.1.0 \\
      --eval-freq 25000 \\
      --tensorboard

  # 实时观看训练进度（另开终端）
  tensorboard --logdir models/ai/v1/dev/tensorboard

  # 从 checkpoint 恢复训练
  python training/train_maskable_ppo.py \\
      --resume models/ai/v1/dev/checkpoints/model_100000_steps.zip \\
      --total-timesteps 1000000
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai_env import (
    ClapClapEnv,
    DEFAULT_OPPONENT_POOL,
    hard_heuristic_policy,
    make_opponent_pool,
    normal_heuristic_policy,
    random_opponent_policy,
    validate_model_metadata,
)


# ---------------------------------------------------------------------------
# manifest helpers
# ---------------------------------------------------------------------------


def build_training_manifest(args: argparse.Namespace) -> dict:
    env = ClapClapEnv(
        ai_player=1,
        max_rounds=args.max_rounds,
        history_window=args.history_window,
        seed=args.seed,
    )
    metadata = env.metadata()
    return {
        "manifest_version": "clapclap-ai-model-manifest-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "MaskablePPO",
        "model_version": args.model_version,
        "inference_adapter": "sb3_maskable_ppo_v1",
        "status": "dry_run" if args.dry_run else "training_requested",
        "env_metadata": metadata,
        "training": {
            "seed": args.seed,
            "total_timesteps": args.total_timesteps,
            "opponent_pool": getattr(args, "opponent_pool", "mixed"),
            "opponent_weights": getattr(args, "opponent_weights", None),
            "seat_randomization": True,
            "max_rounds": args.max_rounds,
            "history_window": args.history_window,
        },
        "evaluation": {
            "required_command": (
                "python scripts/evaluate_ai.py --model-dir <OUTPUT_DIR> "
                "--matrix --games 200 --max-rounds 200 --summary"
            ),
        },
    }


def write_manifest(output_dir: Path, manifest: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "manifest.json"
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


# ---------------------------------------------------------------------------
# dependency guard
# ---------------------------------------------------------------------------


def _ensure_training_dependencies_available() -> None:
    missing: list[str] = []
    for package in ("gymnasium", "torch", "stable_baselines3", "sb3_contrib"):
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        raise SystemExit(
            "Training dependencies are not installed: "
            + ", ".join(missing)
            + ". Install with: pip install -r requirements-train.txt"
        )


# ---------------------------------------------------------------------------
# training loop
# ---------------------------------------------------------------------------


def _resolve_opponent_pool(args: argparse.Namespace):
    """根据 --opponent-pool 参数解析对手策略。"""
    pool_name = args.opponent_pool
    if pool_name == "random":
        return random_opponent_policy
    if pool_name == "mixed":
        weights = args.opponent_weights or [0.2, 0.4, 0.4]
        return make_opponent_pool(
            policies=[random_opponent_policy, normal_heuristic_policy, hard_heuristic_policy],
            weights=weights,
            seed=args.seed + 1,
        )
    # 自定义权重：如 "random:0.3,normal:0.3,hard:0.4"
    if ":" in pool_name:
        parts = [p.strip() for p in pool_name.split(",")]
        policy_map = {
            "random": random_opponent_policy,
            "normal": normal_heuristic_policy,
            "hard": hard_heuristic_policy,
        }
        policies = []
        weights = []
        for part in parts:
            name, _, w = part.partition(":")
            name = name.strip()
            if name not in policy_map:
                raise SystemExit(f"未知对手策略: {name}（可选: random, normal, hard）")
            policies.append(policy_map[name])
            weights.append(float(w.strip()))
        return make_opponent_pool(policies=policies, weights=weights, seed=args.seed + 1)
    raise SystemExit(f"未知 --opponent-pool: {pool_name}（可选: random, mixed, 或 'random:0.2,normal:0.4,hard:0.4'）")


def run_training(args: argparse.Namespace) -> None:
    """Real MaskablePPO training loop with periodic evaluation."""
    _ensure_training_dependencies_available()

    import numpy as np
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
    from stable_baselines3.common.callbacks import (
        BaseCallback,
        CheckpointCallback,
    )
    from stable_baselines3.common.vec_env import DummyVecEnv
    from training.gym_env import make_gymnasium_env

    # ── opponent pool ───────────────────────────────────────────
    opponent_policy = _resolve_opponent_pool(args)

    # ── env factory ──────────────────────────────────────────────
    def _make_env():
        env = make_gymnasium_env(
            ai_player=1,
            opponent_policy=opponent_policy,
            max_rounds=args.max_rounds,
            history_window=args.history_window,
            seed=args.seed,
            randomize_seat=True,
        )

        def _mask_fn(e):
            return e.action_masks()

        return ActionMasker(env, _mask_fn)

    gym_env = _make_env()

    # ── 自定义评估回调（支持 action mask） ───────────────────────
    class MaskedEvalCallback(BaseCallback):
        """定期用当前模型跑评估对局，正确传递 action mask。"""

        def __init__(
            self,
            eval_env_factory,
            eval_freq: int,
            n_eval_episodes: int,
            verbose: int = 0,
        ):
            super().__init__(verbose)
            self._env_factory = eval_env_factory
            self.eval_freq = eval_freq
            self.n_eval_episodes = n_eval_episodes
            self._eval_env: object | None = None

        def _on_step(self) -> bool:
            if self.n_calls % self.eval_freq != 0:
                return True

            if self._eval_env is None:
                self._eval_env = DummyVecEnv([self._env_factory])

            rewards: list[float] = []
            lengths: list[int] = []
            for _ in range(self.n_eval_episodes):
                obs = self._eval_env.reset()
                done = [False]
                ep_reward = 0.0
                ep_len = 0
                while not done[0]:
                    mask = self._eval_env.env_method("action_masks")[0]
                    action, _ = self.model.predict(
                        obs, action_masks=mask, deterministic=True
                    )
                    obs, reward, done, _info = self._eval_env.step(action)
                    ep_reward += float(reward[0])
                    ep_len += 1
                rewards.append(ep_reward)
                lengths.append(ep_len)

            mean_r = float(np.mean(rewards))
            mean_len = float(np.mean(lengths))
            win_rate = sum(1.0 for r in rewards if r > 0) / len(rewards)

            self.logger.record("eval/mean_reward", mean_r)
            self.logger.record("eval/mean_ep_length", mean_len)
            self.logger.record("eval/win_rate", win_rate)

            print(
                f"  [评估] 步={self.num_timesteps:,}  "
                f"avg奖励={mean_r:+.3f}  "
                f"avg回合={mean_len:.1f}  "
                f"胜率={win_rate:.1%}  "
                f"({self.n_eval_episodes}局)"
            )
            return True

    # ── callbacks ─────────────────────────────────────────────────
    callbacks: list = []

    # Checkpoint
    if args.checkpoint_freq > 0:
        checkpoint_dir = args.output_dir / "checkpoints"
        callbacks.append(
            CheckpointCallback(
                save_freq=args.checkpoint_freq,
                save_path=str(checkpoint_dir),
                name_prefix="model",
                save_replay_buffer=False,
                save_vecnormalize=False,
            )
        )

    # 定期评估（使用自定义回调，支持 action mask）
    if args.eval_freq > 0:
        callbacks.append(
            MaskedEvalCallback(
                eval_env_factory=_make_env,
                eval_freq=args.eval_freq,
                n_eval_episodes=args.eval_episodes,
            )
        )

    # ── model ────────────────────────────────────────────────────
    tensorboard_log = str(args.output_dir / "tensorboard") if args.tensorboard else None

    if args.resume:
        print(f"[resume] 从 checkpoint 加载: {args.resume}")
        model = MaskablePPO.load(
            str(args.resume),
            env=gym_env,
            tensorboard_log=tensorboard_log,
            seed=args.seed,
        )
        # 恢复时保持 verbose=1
        model.verbose = 1
    else:
        model = MaskablePPO(
            "MlpPolicy",
            gym_env,
            verbose=1,
            seed=args.seed,
            tensorboard_log=tensorboard_log,
            # 默认 MLP 策略网络：[64, 64] 两层，适合 32 维观测
            policy_kwargs=dict(net_arch=[64, 64]),
        )

    # ── 训练前信息 ───────────────────────────────────────────────
    _print_training_header(args, model)

    # ── train ────────────────────────────────────────────────────
    t0 = time.perf_counter()
    model.learn(
        total_timesteps=args.total_timesteps,
        callback=callbacks if callbacks else None,
        tb_log_name="clapclap_v1",
        reset_num_timesteps=not bool(args.resume),
    )
    elapsed_s = time.perf_counter() - t0

    # ── save ─────────────────────────────────────────────────────
    weights_filename = "model"
    model.save(str(args.output_dir / weights_filename))
    weights_path = args.output_dir / f"{weights_filename}.zip"

    manifest = build_training_manifest(args)
    manifest["status"] = "trained"
    manifest["weights_path"] = f"{weights_filename}.zip"
    manifest["training"]["wall_clock_seconds"] = round(elapsed_s, 1)
    manifest_path = write_manifest(args.output_dir, manifest)

    _print_training_footer(elapsed_s, weights_path, manifest_path, args)


def _print_training_header(args: argparse.Namespace, model: object) -> None:
    """打印训练开始前的配置信息。"""
    n_params = sum(p.numel() for p in model.policy.parameters())  # type: ignore[union-attr]
    print()
    print("═" * 55)
    print("  ClapClap 1.0 AI — MaskablePPO 训练")
    print("═" * 55)
    print(f"  模型版本:     {args.model_version}")
    print(f"  输出目录:     {args.output_dir}")
    print(f"  总步数:       {args.total_timesteps:,}")
    print(f"  对手池:       {args.opponent_pool}")
    if getattr(args, "opponent_weights", None):
        print(f"  对手权重:     {args.opponent_weights}")
    print(f"  座位:         每局随机 P1/P2")
    print(f"  最大回合:     {args.max_rounds}")
    print(f"  历史窗口:     {args.history_window}")
    print(f"  网络参数:     {n_params:,}")
    print(f"  Seed:         {args.seed}")
    if args.tensorboard:
        print(f"  TensorBoard:  {args.output_dir / 'tensorboard'}")
    if args.eval_freq > 0:
        print(f"  定期评估:     每 {args.eval_freq:,} 步 ({args.eval_episodes} 局)")
    if args.checkpoint_freq > 0:
        print(f"  Checkpoint:   每 {args.checkpoint_freq:,} 步")
    print("─" * 55)
    if args.tensorboard:
        print(f"  实时监控: tensorboard --logdir {args.output_dir / 'tensorboard'}")
    print()


def _print_training_footer(
    elapsed_s: float,
    weights_path: Path,
    manifest_path: Path,
    args: argparse.Namespace,
) -> None:
    """打印训练结束后的汇总信息。"""
    print()
    print("═" * 55)
    print(f"  ✓ 训练完成（{elapsed_s/60:.1f} 分钟）")
    print(f"  模型:  {weights_path}")
    print(f"  清单:  {manifest_path}")
    print("─" * 55)
    print(f"  下一步:")
    print(f"  1. 离线评估:")
    print(f"     python scripts/evaluate_ai.py --model-dir {args.output_dir} \\")
    print(f"         --matrix --games 200 --max-rounds 200 --summary")
    print(f"  2. 晋级到 deploy:")
    print(f"     python scripts/promote_ai_model.py --model-dir {args.output_dir} \\")
    print(f"         --auto-eval --eval-games 200")
    print("═" * 55)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train ClapClap 1.0 AI with Maskable PPO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # ── 核心参数 ──
    g_core = parser.add_argument_group("核心参数")
    g_core.add_argument(
        "--output-dir", type=Path, default=Path("models/ai/v1/dev"),
        help="模型输出目录。默认: models/ai/v1/dev",
    )
    g_core.add_argument(
        "--model-version", default="dev",
        help="模型版本名，写入 manifest。默认: dev",
    )
    g_core.add_argument(
        "--total-timesteps", type=int, default=100_000,
        help="训练总步数。推荐: 500000+  (默认: 100000)",
    )
    g_core.add_argument("--seed", type=int, default=20260630)

    # ── 环境参数 ──
    g_env = parser.add_argument_group("环境参数")
    g_env.add_argument("--max-rounds", type=int, default=200)
    g_env.add_argument("--history-window", type=int, default=4)
    g_env.add_argument(
        "--opponent-pool",
        default="mixed",
        help="对手池: random | mixed (random+normal+hard) | 自定义如 random:0.2,normal:0.4,hard:0.4",
    )
    g_env.add_argument(
        "--opponent-weights",
        type=float,
        nargs="*",
        help="对手池权重（仅 --opponent-pool mixed 时生效）。默认: 0.2 0.4 0.4",
    )

    # ── 进度监控 ──
    g_mon = parser.add_argument_group("进度监控")
    g_mon.add_argument(
        "--tensorboard",
        action="store_true",
        help="启用 TensorBoard 日志（强烈推荐）。"
        " 另开终端运行: tensorboard --logdir <output_dir>/tensorboard",
    )
    g_mon.add_argument(
        "--eval-freq",
        type=int,
        default=0,
        help="定期评估频率（步）。如 25000 表示每 25000 步评估一次。默认: 0 (不评估)",
    )
    g_mon.add_argument(
        "--eval-episodes",
        type=int,
        default=50,
        help="每次评估运行的对局数。默认: 50",
    )
    g_mon.add_argument(
        "--checkpoint-freq",
        type=int,
        default=0,
        help="保存 checkpoint 的频率（步）。如 50000。默认: 0 (不保存)",
    )

    # ── 恢复训练 ──
    g_resume = parser.add_argument_group("恢复训练")
    g_resume.add_argument(
        "--resume",
        type=Path,
        help="从 checkpoint 或已保存模型恢复训练。",
    )

    # ── 快速模式 ──
    g_quick = parser.add_argument_group("快速模式")
    g_quick.add_argument(
        "--dry-run",
        action="store_true",
        help="只验证 manifest 不训练。",
    )
    g_quick.add_argument(
        "--smoke-test",
        action="store_true",
        help="最小训练验证全链路（2000 步）。",
    )
    args = parser.parse_args()

    # ── smoke-test shorthand ─────────────────────────────────
    if args.smoke_test:
        args.total_timesteps = 2000
        args.model_version = (
            f"smoke-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )
        if args.checkpoint_freq == 0:
            args.checkpoint_freq = 1000
        if args.eval_freq == 0:
            args.eval_freq = 1000
            args.eval_episodes = 20

    # ── 自动版本名 ───────────────────────────────────────────
    if args.model_version == "dev" and not args.dry_run and not args.smoke_test:
        args.model_version = (
            f"dev-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )

    # ── validation ───────────────────────────────────────────
    if args.total_timesteps <= 0:
        raise SystemExit("--total-timesteps must be greater than 0")
    if args.max_rounds <= 0:
        raise SystemExit("--max-rounds must be greater than 0")
    if args.history_window < 0:
        raise SystemExit("--history-window cannot be negative")
    if args.eval_episodes <= 0:
        raise SystemExit("--eval-episodes must be greater than 0")

    # ── resume 路径处理 ──────────────────────────────────────
    if args.resume:
        args.resume = args.resume.resolve()
        if not args.resume.exists():
            raise SystemExit(f"Checkpoint 不存在: {args.resume}")

    # ── manifest (always validated before touching heavy deps) ──
    manifest = build_training_manifest(args)
    if not validate_model_metadata(manifest["env_metadata"]):
        raise SystemExit(
            "Generated env metadata does not match current ClapClapEnv contract."
        )

    if args.dry_run:
        path = write_manifest(args.output_dir, manifest)
        print(f"dry-run manifest written: {path}")
        return

    # ── 确认输出目录 ─────────────────────────────────────────
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        write_manifest(args.output_dir, manifest)

    # ── real training ────────────────────────────────────────
    run_training(args)


if __name__ == "__main__":
    main()
