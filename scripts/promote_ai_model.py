"""Promote a candidate AI model to deployable status.

Evaluates a trained model directory (manifest.json + weights) against the
promotion thresholds defined in task.txt. Only models that pass all checks
are copied to the deploy directory.

Usage
-----
  # 1. Run evaluation against the candidate model
  python scripts/evaluate_ai.py --model-dir models/ai/v1/dev --matrix \\
      --games 200 --max-rounds 200 --output reports/ai_eval/candidate.json

  # 2. Promote if evaluation passes
  python scripts/promote_ai_model.py --model-dir models/ai/v1/dev \\
      --eval-report reports/ai_eval/candidate.json

  # Or let promote run the evaluation automatically (slower)
  python scripts/promote_ai_model.py --model-dir models/ai/v1/dev --auto-eval
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai_env import validate_model_metadata

# ── 默认晋级阈值（来自 task.txt 阶段 B） ──────────────────────────
DEFAULT_THRESHOLDS: dict[str, Any] = {
    "max_illegal_moves": 0,
    "max_truncated_rate": 0.05,
    "model_vs_easy_min_win_rate": 0.94,       # 不低于 normal baseline
    "model_vs_normal_min_win_rate": 0.60,       # 必须明显强于 normal
    "model_vs_random_min_win_rate": 0.85,       # 必须显著高于随机（随机期望胜率 ≈50%）
    "max_seat_win_rate_delta": 0.30,            # P1/P2 胜率差
    "max_double_loss_rate": 0.05,               # 双败率（双方同时死亡 ratio）
    "max_action_concentration": 0.90,            # 单一动作最大占比
    "max_fallback_rate": 0.10,                  # 模型推理回退率上限
}

DEPLOY_DIR = Path("models/ai/v1/deploy")
ARCHIVE_DIR = Path("models/ai/v1/archive")


# ── 阈值检查 ──────────────────────────────────────────────────────


def _get_matrix_entry(report: dict, key: str) -> dict | None:
    """从评估报告中取出某个 matchup 的汇总数据。"""
    if report.get("report_type") == "clapclap_ai_matrix":
        return report.get("matrix", {}).get(key)
    # 单组评估：key 匹配到 ai_vs_opponent
    label = f"{report.get('ai_difficulty', '')}_vs_{report.get('opponent_difficulty', '')}"
    if label == key:
        return report
    return None


def check_thresholds(
    report: dict,
    thresholds: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """返回 ``(passed, reasons)``。"""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    failures: list[str] = []

    results = report.get("results", [report])

    # 1. 全局 illegal_moves == 0
    total_illegal = sum(r.get("illegal_moves", 0) for r in results)
    if total_illegal > t["max_illegal_moves"]:
        failures.append(f"illegal_moves={total_illegal} (max={t['max_illegal_moves']})")

    # 2. truncated_rate 检查
    for r in results:
        label = f"{r.get('ai_difficulty', '?')}_vs_{r.get('opponent_difficulty', '?')}"
        truncated = r.get("truncated_rate", 0)
        if truncated > t["max_truncated_rate"]:
            failures.append(
                f"{label} truncated_rate={truncated:.4f} (max={t['max_truncated_rate']})"
            )

    # 3. model_vs_easy 胜率
    vs_easy = _get_matrix_entry(report, "model_vs_easy")
    if vs_easy:
        wr = vs_easy.get("win_rate", 0)
        if wr < t["model_vs_easy_min_win_rate"]:
            failures.append(
                f"model_vs_easy win_rate={wr:.4f} (min={t['model_vs_easy_min_win_rate']})"
            )

    # 4. model_vs_normal 胜率
    vs_normal = _get_matrix_entry(report, "model_vs_normal")
    if vs_normal:
        wr = vs_normal.get("win_rate", 0)
        if wr < t["model_vs_normal_min_win_rate"]:
            failures.append(
                f"model_vs_normal win_rate={wr:.4f} (min={t['model_vs_normal_min_win_rate']})"
            )

    # 5. model_vs_random 胜率
    vs_random = _get_matrix_entry(report, "model_vs_random")
    if vs_random:
        wr = vs_random.get("win_rate", 0)
        if wr < t["model_vs_random_min_win_rate"]:
            failures.append(
                f"model_vs_random win_rate={wr:.4f} (min={t['model_vs_random_min_win_rate']})"
            )

    # 6. P1/P2 胜率差
    for r in results:
        label = f"{r.get('ai_difficulty', '?')}_vs_{r.get('opponent_difficulty', '?')}"
        delta = abs(r.get("p1_win_rate", 0) - r.get("p2_win_rate", 0))
        if delta > t["max_seat_win_rate_delta"]:
            failures.append(
                f"{label} seat_win_rate_delta={delta:.4f} (max={t['max_seat_win_rate_delta']})"
            )

    # 7. 双败率
    for r in results:
        label = f"{r.get('ai_difficulty', '?')}_vs_{r.get('opponent_difficulty', '?')}"
        dlr = r.get("double_lose_rate", r.get("draw_rate", 0))
        if dlr > t["max_double_loss_rate"]:
            failures.append(
                f"{label} double_lose_rate={dlr:.4f} (max={t['max_double_loss_rate']})"
            )

    # 8. 动作分布极端坍缩
    for r in results:
        action_counts = r.get("action_counts", {})
        if action_counts:
            total = sum(action_counts.values())
            max_ratio = max(action_counts.values()) / total if total > 0 else 0
            if max_ratio > t["max_action_concentration"]:
                top_action = max(action_counts, key=action_counts.get)
                label = f"{r.get('ai_difficulty', '?')}_vs_{r.get('opponent_difficulty', '?')}"
                failures.append(
                    f"{label} action_concentration={max_ratio:.4f} "
                    f"(action={top_action}) > {t['max_action_concentration']}"
                )

    # 9. fallback_rate 检查
    for r in results:
        fallback_rate = r.get("fallback_rate", 0)
        if fallback_rate > t["max_fallback_rate"]:
            label = f"{r.get('ai_difficulty', '?')}_vs_{r.get('opponent_difficulty', '?')}"
            failures.append(
                f"{label} fallback_rate={fallback_rate:.4f} (max={t['max_fallback_rate']})"
            )

    return len(failures) == 0, failures


# ── 执行 promote ───────────────────────────────────────────────────


def promote(
    model_dir: Path,
    eval_report: dict,
    *,
    thresholds: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """执行晋级操作。返回 ``(success, message)``。"""

    # 1. 校验 manifest
    manifest_path = model_dir / "manifest.json"
    if not manifest_path.exists():
        return False, f"manifest 不存在: {manifest_path}"

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"manifest 不可读: {exc}"

    env_meta = manifest.get("env_metadata", {})
    if not isinstance(env_meta, dict) or not validate_model_metadata(env_meta):
        return False, "manifest metadata 校验失败（规则版本/动作空间/观察空间不匹配）"

    weights_rel = manifest.get("weights_path", "model.zip")
    weights_path = model_dir / weights_rel
    if not weights_path.exists():
        return False, f"权重文件不存在: {weights_path}"

    # 2. 阈值检查
    passed, failures = check_thresholds(eval_report, thresholds)
    if not passed:
        return False, "晋级阈值未通过:\n  " + "\n  ".join(failures)

    # 3. 复制到 deploy 目录
    model_version = manifest.get("model_version", "unknown")
    if dry_run:
        return True, f"[dry-run] {model_version} 通过所有阈值检查，可晋级"

    # 先归档当前 deploy 模型
    deploy_manifest = DEPLOY_DIR / "manifest.json"
    if deploy_manifest.exists():
        archive_version_dir = _archive_current_deploy()
        if archive_version_dir:
            print(f"[promote] 已归档当前 deploy → {archive_version_dir}")

    # 清理并复制
    if DEPLOY_DIR.exists():
        shutil.rmtree(DEPLOY_DIR)
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, DEPLOY_DIR / "manifest.json")
    shutil.copy2(weights_path, DEPLOY_DIR / weights_rel)

    # 写入 deploy 专属信息
    deploy_meta = json.loads((DEPLOY_DIR / "manifest.json").read_text(encoding="utf-8"))
    deploy_meta["status"] = "deployed"
    deploy_meta["promoted_at"] = datetime.now(timezone.utc).isoformat()
    deploy_meta["promotion"] = {
        "source_dir": str(model_dir.resolve()),
        "thresholds": {**DEFAULT_THRESHOLDS, **(thresholds or {})},
        "checks_passed": True,
    }
    (DEPLOY_DIR / "manifest.json").write_text(
        json.dumps(deploy_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 如果有评估报告，一并复制
    eval_dest = DEPLOY_DIR / "evaluation_report.json"
    eval_dest.write_text(
        json.dumps(eval_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return True, f"✓ {model_version} 已晋级到 {DEPLOY_DIR}"


def _archive_current_deploy() -> Path | None:
    """将当前 deploy 目录移动到 archive。"""
    if not DEPLOY_DIR.exists():
        return None
    try:
        deploy_manifest = json.loads(
            (DEPLOY_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        version = deploy_manifest.get("model_version", "unknown")
    except Exception:
        version = "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = ARCHIVE_DIR / f"{version}_{ts}"
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(DEPLOY_DIR), str(archive_dir))
    if DEPLOY_DIR.exists():
        shutil.rmtree(DEPLOY_DIR)
    return archive_dir


# ── CLI ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote a trained AI model to deployable status."
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        required=True,
        help="Candidate model directory (contains manifest.json + weights).",
    )
    parser.add_argument(
        "--eval-report",
        type=Path,
        help="Path to a JSON evaluation report from evaluate_ai.py.",
    )
    parser.add_argument(
        "--auto-eval",
        action="store_true",
        help="Run evaluation automatically before checking thresholds.",
    )
    parser.add_argument(
        "--eval-games", type=int, default=200, help="Games per matchup for --auto-eval."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check thresholds and report result without copying files.",
    )
    parser.add_argument(
        "--min-win-rate-vs-easy", type=float,
    )
    parser.add_argument(
        "--min-win-rate-vs-normal", type=float,
    )
    parser.add_argument(
        "--max-truncated-rate", type=float,
    )
    parser.add_argument(
        "--max-seat-delta", type=float,
    )
    args = parser.parse_args()

    model_dir = args.model_dir.resolve()
    if not model_dir.is_dir():
        raise SystemExit(f"模型目录不存在: {model_dir}")

    # ── 获取评估报告 ────────────────────────────────────────
    eval_report: dict | None = None
    if args.eval_report:
        if not args.eval_report.exists():
            raise SystemExit(f"评估报告不存在: {args.eval_report}")
        eval_report = json.loads(args.eval_report.read_text(encoding="utf-8"))
    elif args.auto_eval:
        print("[promote] 自动运行评估矩阵...")
        from scripts.evaluate_ai import ModelEvaluator, evaluate_matrix

        model = ModelEvaluator(model_dir, max_rounds=200)
        if not model.is_loaded:
            raise SystemExit(f"模型加载失败: {model.info.load_error}")
        eval_report = evaluate_matrix(
            games=args.eval_games,
            seed=20260630,
            max_rounds=200,
            model=model,
        )
    else:
        raise SystemExit(
            "需要 --eval-report 或 --auto-eval 提供评估报告。"
        )

    # ── 构建阈值 ────────────────────────────────────────────
    thresholds: dict[str, Any] = {}
    if args.min_win_rate_vs_easy is not None:
        thresholds["model_vs_easy_min_win_rate"] = args.min_win_rate_vs_easy
    if args.min_win_rate_vs_normal is not None:
        thresholds["model_vs_normal_min_win_rate"] = args.min_win_rate_vs_normal
    if args.max_truncated_rate is not None:
        thresholds["max_truncated_rate"] = args.max_truncated_rate
    if args.max_seat_delta is not None:
        thresholds["max_seat_win_rate_delta"] = args.max_seat_delta

    # ── 执行 ────────────────────────────────────────────────
    success, message = promote(
        model_dir,
        eval_report,
        thresholds=thresholds,
        dry_run=args.dry_run,
    )
    print(message)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
