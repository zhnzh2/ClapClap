from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai.engine import get_legal_action_mask, get_legal_moves_list, select_move
from app.ai_env import validate_model_metadata
from app.v1.game import GameEngine
from app.v1.models import GameState

Difficulty = Literal["easy", "normal", "hard"]
PolicyType = Literal["easy", "normal", "hard", "random", "model"]
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "normal", "hard")
DEFAULT_MATRIX: tuple[tuple[Difficulty, Difficulty], ...] = (
    ("easy", "easy"),
    ("normal", "easy"),
    ("hard", "easy"),
    ("hard", "normal"),
    ("normal", "hard"),
)
MODEL_MATRIX: tuple[tuple[PolicyType, PolicyType], ...] = (
    ("model", "easy"),
    ("model", "normal"),
    ("model", "hard"),
    ("model", "random"),
)


@dataclass
class EvaluationResult:
    games: int
    ai_difficulty: str
    opponent_difficulty: str
    ai_wins: int = 0
    opponent_wins: int = 0
    draws: int = 0
    truncated: int = 0
    illegal_moves: int = 0
    total_rounds: int = 0
    ai_as_p1_games: int = 0
    ai_as_p2_games: int = 0
    ai_as_p1_wins: int = 0
    ai_as_p2_wins: int = 0
    ai_flash_uses: int = 0
    ai_pickaxe_actions: int = 0
    ai_final_hp_total: int = 0
    opponent_final_hp_total: int = 0
    ai_final_qi_total: int = 0
    ai_final_shield_total: int = 0
    opponent_final_qi_total: int = 0
    opponent_final_shield_total: int = 0
    inference_calls: int = 0
    total_inference_ms: float = 0.0
    max_inference_ms: float = 0.0
    fallback_count: int = 0
    timeout_count: int = 0
    inference_samples_ms: list[float] = field(default_factory=list, repr=False)

    @property
    def win_rate(self) -> float:
        return round(self.ai_wins / self.games, 4) if self.games else 0.0

    @property
    def loss_rate(self) -> float:
        return round(self.opponent_wins / self.games, 4) if self.games else 0.0

    @property
    def draw_rate(self) -> float:
        return round(self.draws / self.games, 4) if self.games else 0.0

    @property
    def truncated_rate(self) -> float:
        return round(self.truncated / self.games, 4) if self.games else 0.0

    @property
    def average_rounds(self) -> float:
        return round(self.total_rounds / self.games, 2) if self.games else 0.0

    @property
    def p1_win_rate(self) -> float:
        return round(self.ai_as_p1_wins / self.ai_as_p1_games, 4) if self.ai_as_p1_games else 0.0

    @property
    def p2_win_rate(self) -> float:
        return round(self.ai_as_p2_wins / self.ai_as_p2_games, 4) if self.ai_as_p2_games else 0.0

    @property
    def seat_win_rate_delta(self) -> float:
        return round(abs(self.p1_win_rate - self.p2_win_rate), 4)

    @property
    def average_ai_final_hp(self) -> float:
        return round(self.ai_final_hp_total / self.games, 2) if self.games else 0.0

    @property
    def average_opponent_final_hp(self) -> float:
        return round(self.opponent_final_hp_total / self.games, 2) if self.games else 0.0

    @property
    def average_ai_final_qi(self) -> float:
        return round(self.ai_final_qi_total / self.games, 2) if self.games else 0.0

    @property
    def average_ai_final_shield(self) -> float:
        return round(self.ai_final_shield_total / self.games, 2) if self.games else 0.0

    @property
    def average_opponent_final_qi(self) -> float:
        return round(self.opponent_final_qi_total / self.games, 2) if self.games else 0.0

    @property
    def average_opponent_final_shield(self) -> float:
        return round(self.opponent_final_shield_total / self.games, 2) if self.games else 0.0

    @property
    def double_lose_rate(self) -> float:
        """双方同时死亡（winner=0）的比率，等价于 draw_rate。"""
        return self.draw_rate

    @property
    def fallback_rate(self) -> float:
        if not self.inference_calls:
            return 0.0
        return round(self.fallback_count / self.inference_calls, 4)

    @property
    def average_inference_ms(self) -> float:
        if not self.inference_calls:
            return 0.0
        return round(self.total_inference_ms / self.inference_calls, 4)

    @property
    def p95_inference_ms(self) -> float:
        if not self.inference_samples_ms:
            return 0.0
        ordered = sorted(self.inference_samples_ms)
        index = max(0, min(len(ordered) - 1, (95 * len(ordered) + 99) // 100 - 1))
        return round(ordered[index], 4)

    @property
    def timeout_rate(self) -> float:
        if not self.inference_calls:
            return 0.0
        return round(self.timeout_count / self.inference_calls, 4)


# ---------------------------------------------------------------------------
# 模型评估器
# ---------------------------------------------------------------------------


@dataclass
class ModelEvalInfo:
    """加载模型时的元信息，会写入评估报告。"""

    model_version: str = ""
    manifest_path: str = ""
    weights_path: str = ""
    algorithm: str = ""
    inference_adapter: str = ""
    training_timesteps: int = 0
    load_error: str = ""


class ModelEvaluator:
    """加载训练好的模型并提供推理接口。

    仅在 ``--model-dir`` 指定时才尝试加载；加载失败时标记 ``load_error``
    并回退到 heuristic hard，评估报告会记录失败原因。
    """

    def __init__(
        self,
        model_dir: Path,
        max_rounds: int,
        inference_timeout_ms: float | None = None,
    ):
        self.model_dir = model_dir
        self.max_rounds = max_rounds
        self.info = ModelEvalInfo()
        self._model: object | None = None
        self._loaded = False
        self.fallback_count: int = 0
        self.timeout_count: int = 0
        self.inference_timeout_ms = inference_timeout_ms or float(
            os.environ.get("CLAPCLAP_AI_INFERENCE_TIMEOUT_MS", "100")
        )
        self._load()

    # ── 公开属性 ────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return self._loaded and self._model is not None

    # ── 推理 ────────────────────────────────────────────────────

    def select_move(
        self, state: GameState, player: int, rng: random.Random
    ) -> tuple[object, float]:
        """返回 ``(move, elapsed_ms)``。未加载或推理失败时回退 heuristic-hard。"""
        if not self.is_loaded:
            self.fallback_count += 1
            return self._heuristic_fallback(state, player, rng)

        import numpy as np
        from training.gym_env import encode_observation_vector

        t0 = time.perf_counter()
        try:
            obs_dict = self._build_observation(state, player)
            vec = np.array(
                encode_observation_vector(obs_dict, max_rounds=self.max_rounds),
                dtype=np.float32,
            )
            mask = np.array(obs_dict["legal_action_mask"], dtype=bool)

            action_index, _ = self._model.predict(  # type: ignore[union-attr]
                vec, action_masks=mask, deterministic=True
            )
            action_int = int(action_index)
            from app.ai.space import get_move_by_index

            move = get_move_by_index(action_int)
            if not mask[action_int]:
                self.fallback_count += 1
                return self._heuristic_fallback(state, player, rng)
        except Exception:
            self.fallback_count += 1
            return self._heuristic_fallback(state, player, rng)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms > self.inference_timeout_ms:
            self.timeout_count += 1
        return move, elapsed_ms

    # ── 内部 ────────────────────────────────────────────────────

    def _load(self) -> None:
        manifest_path = self.model_dir / "manifest.json"
        if not manifest_path.exists():
            self.info.load_error = "manifest_missing"
            return

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.info.load_error = f"manifest_unreadable:{exc.__class__.__name__}"
            return

        env_meta = manifest.get("env_metadata", {})
        if not isinstance(env_meta, dict) or not validate_model_metadata(env_meta):
            self.info.load_error = "metadata_mismatch"
            return

        weights_rel = manifest.get("weights_path", "model.zip")
        weights_path = self.model_dir / weights_rel
        if not weights_path.exists():
            self.info.load_error = f"weights_missing:{weights_rel}"
            return

        try:
            from sb3_contrib import MaskablePPO

            model_path = str(weights_path).replace(".zip", "")
            self._model = MaskablePPO.load(model_path)
        except Exception as exc:
            self.info.load_error = f"model_load_failed:{exc.__class__.__name__}"
            return

        self._loaded = True
        training = manifest.get("training", {})
        self.info = ModelEvalInfo(
            model_version=manifest.get("model_version", ""),
            manifest_path=str(manifest_path),
            weights_path=str(weights_path),
            algorithm=manifest.get("algorithm", ""),
            inference_adapter=manifest.get("inference_adapter", ""),
            training_timesteps=training.get("total_timesteps", 0),
        )

    @staticmethod
    def _build_observation(state: GameState, player: int) -> dict:
        self_p = (state.p1 if player == 1 else state.p2).to_dict()
        opp_p = (state.p2 if player == 1 else state.p1).to_dict()
        mask = get_legal_action_mask(state, player)
        return {
            "round_num": state.round_num,
            "self": self_p,
            "opponent": opp_p,
            "legal_action_mask": mask,
        }

    @staticmethod
    def _heuristic_fallback(
        state: GameState, player: int, rng: random.Random
    ) -> tuple[object, float]:
        t0 = time.perf_counter()
        move = select_move(
            state.copy(), player, rng, {"difficulty": "hard"}
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return move, elapsed_ms


# ---------------------------------------------------------------------------
# 评估核心
# ---------------------------------------------------------------------------


def _choose_move(
    state: GameState,
    player: int,
    difficulty: Difficulty | str,
    rng: random.Random,
    model: ModelEvaluator | None = None,
) -> tuple[object, float]:
    if difficulty == "model" and model is not None:
        return model.select_move(state, player, rng)
    started = time.perf_counter()
    move = select_move(state.copy(), player, rng, {"difficulty": difficulty})
    elapsed_ms = (time.perf_counter() - started) * 1000
    return move, elapsed_ms


def _player_state(state: GameState, player: int):
    return state.p1 if player == 1 else state.p2


def play_game(
    *,
    ai_difficulty: Difficulty | str,
    opponent_difficulty: Difficulty | str,
    ai_player: int,
    rng: random.Random,
    max_rounds: int,
    collect_log: bool = False,
    model: ModelEvaluator | None = None,
    opponent_model: ModelEvaluator | None = None,
) -> dict:
    state = GameState()
    action_counts: Counter = Counter()
    illegal_moves = 0
    ai_flash_uses = 0
    ai_pickaxe_actions = 0
    inference_times_ms: list[float] = []
    rounds_log: list[dict] = []

    fallback_start = model.fallback_count if model is not None else 0
    timeout_start = model.timeout_count if model is not None else 0

    while state.winner is None and state.round_num < max_rounds:
        round_start = state.copy()
        opponent_player = 2 if ai_player == 1 else 1
        ai_legal = [move.name for move in get_legal_moves_list(round_start, ai_player)]
        opponent_legal = [
            move.name for move in get_legal_moves_list(round_start, opponent_player)
        ]

        ai_move, ai_elapsed_ms = _choose_move(
            round_start, ai_player, ai_difficulty, rng, model=model
        )
        opponent_move, _ = _choose_move(
            round_start,
            opponent_player,
            opponent_difficulty,
            rng,
            model=opponent_model if opponent_difficulty == "model" else model,
        )
        inference_times_ms.append(ai_elapsed_ms)

        if ai_player == 1:
            p1_move, p2_move = ai_move, opponent_move
        else:
            p1_move, p2_move = opponent_move, ai_move

        GameEngine.resolve_round(state, p1_move, p2_move)
        if collect_log:
            rounds_log.append({
                "round_num": round_start.round_num + 1,
                "round_start_state": round_start.to_dict(include_history=False),
                "ai_player": ai_player,
                "ai_legal_actions": ai_legal,
                "opponent_legal_actions": opponent_legal,
                "ai_move": ai_move.name,
                "opponent_move": opponent_move.name,
                "p1_move": p1_move.name,
                "p2_move": p2_move.name,
                "round_end_state": state.to_dict(include_history=False),
                "winner": state.winner,
                "truncated": False,
            })
        action_counts[ai_move.name] += 1
        if ai_move.name == "SHAN":
            ai_flash_uses += 1
        if ai_move.name == "GAO":
            ai_pickaxe_actions += 1
        if state.history:
            latest = state.history[-1]
            if ai_player == 1 and not latest.p1_valid:
                illegal_moves += 1
            if ai_player == 2 and not latest.p2_valid:
                illegal_moves += 1

    fallback_count = (
        model.fallback_count - fallback_start if model is not None else 0
    )
    timeout_count = (
        model.timeout_count - timeout_start if model is not None else 0
    )
    opponent_player = 2 if ai_player == 1 else 1
    ai_final = _player_state(state, ai_player)
    opponent_final = _player_state(state, opponent_player)
    return {
        "winner": state.winner,
        "rounds": state.round_num,
        "action_counts": action_counts,
        "illegal_moves": illegal_moves,
        "ai_flash_uses": ai_flash_uses,
        "ai_pickaxe_actions": ai_pickaxe_actions,
        "ai_final": ai_final.to_dict(),
        "opponent_final": opponent_final.to_dict(),
        "inference_times_ms": inference_times_ms,
        "fallback_count": fallback_count,
        "timeout_count": timeout_count,
        "rounds_log": rounds_log,
    }


def evaluate(
    *,
    games: int,
    ai_difficulty: Difficulty | str,
    opponent_difficulty: Difficulty | str,
    seed: int,
    max_rounds: int,
    collect_logs: bool = False,
    model: ModelEvaluator | None = None,
    opponent_model: ModelEvaluator | None = None,
) -> dict:
    if games <= 0:
        raise ValueError("games must be greater than 0")
    if max_rounds <= 0:
        raise ValueError("max_rounds must be greater than 0")

    rng = random.Random(seed)
    result = EvaluationResult(
        games=games,
        ai_difficulty=ai_difficulty,
        opponent_difficulty=opponent_difficulty,
    )
    action_counts: Counter = Counter()
    game_logs: list[dict] = []

    for game_index in range(games):
        ai_player = 1 if game_index % 2 == 0 else 2
        if ai_player == 1:
            result.ai_as_p1_games += 1
        else:
            result.ai_as_p2_games += 1

        game = play_game(
            ai_difficulty=ai_difficulty,
            opponent_difficulty=opponent_difficulty,
            ai_player=ai_player,
            rng=rng,
            max_rounds=max_rounds,
            collect_log=collect_logs,
            model=model,
            opponent_model=opponent_model,
        )
        winner = game["winner"]
        rounds = game["rounds"]
        counts = game["action_counts"]
        illegal = game["illegal_moves"]
        result.total_rounds += rounds
        result.illegal_moves += illegal
        action_counts.update(counts)
        result.ai_flash_uses += game["ai_flash_uses"]
        result.ai_pickaxe_actions += game["ai_pickaxe_actions"]
        result.fallback_count += game.get("fallback_count", 0)
        result.timeout_count += game.get("timeout_count", 0)
        result.inference_calls += len(game["inference_times_ms"])
        result.total_inference_ms += sum(game["inference_times_ms"])
        result.inference_samples_ms.extend(game["inference_times_ms"])
        if game["inference_times_ms"]:
            result.max_inference_ms = max(result.max_inference_ms, max(game["inference_times_ms"]))

        ai_final = game["ai_final"]
        opponent_final = game["opponent_final"]
        result.ai_final_hp_total += ai_final["hp"]
        result.opponent_final_hp_total += opponent_final["hp"]
        result.ai_final_qi_total += ai_final["qi"]
        result.ai_final_shield_total += ai_final["shield"]
        result.opponent_final_qi_total += opponent_final["qi"]
        result.opponent_final_shield_total += opponent_final["shield"]

        if winner is None:
            result.truncated += 1
        elif winner == 0:
            result.draws += 1
        elif winner == ai_player:
            result.ai_wins += 1
            if ai_player == 1:
                result.ai_as_p1_wins += 1
            else:
                result.ai_as_p2_wins += 1
        else:
            result.opponent_wins += 1

        if collect_logs:
            game_logs.append({
                "game_index": game_index,
                "seed": seed,
                "ai_difficulty": ai_difficulty,
                "opponent_difficulty": opponent_difficulty,
                "ai_player": ai_player,
                "winner": winner,
                "rounds": rounds,
                "truncated": winner is None,
                "rounds_log": game["rounds_log"],
            })

    payload = asdict(result)
    payload.pop("inference_samples_ms", None)
    payload["win_rate"] = result.win_rate
    payload["loss_rate"] = result.loss_rate
    payload["draw_rate"] = result.draw_rate
    payload["truncated_rate"] = result.truncated_rate
    payload["average_rounds"] = result.average_rounds
    payload["p1_win_rate"] = result.p1_win_rate
    payload["p2_win_rate"] = result.p2_win_rate
    payload["seat_win_rate_delta"] = result.seat_win_rate_delta
    payload["average_ai_final_hp"] = result.average_ai_final_hp
    payload["average_opponent_final_hp"] = result.average_opponent_final_hp
    payload["average_ai_final_qi"] = result.average_ai_final_qi
    payload["average_ai_final_shield"] = result.average_ai_final_shield
    payload["average_opponent_final_qi"] = result.average_opponent_final_qi
    payload["average_opponent_final_shield"] = result.average_opponent_final_shield
    payload["average_inference_ms"] = result.average_inference_ms
    payload["max_inference_ms"] = round(result.max_inference_ms, 4)
    payload["p95_inference_ms"] = result.p95_inference_ms
    payload["fallback_count"] = result.fallback_count
    payload["fallback_rate"] = result.fallback_rate
    payload["timeout_count"] = result.timeout_count
    payload["timeout_rate"] = result.timeout_rate
    payload["double_lose_rate"] = result.double_lose_rate
    payload["action_counts"] = dict(sorted(action_counts.items()))
    if collect_logs:
        payload["game_logs"] = game_logs
    return payload


def evaluate_matrix(
    *,
    games: int,
    seed: int,
    max_rounds: int,
    matchups: tuple[tuple[str, str], ...] | None = None,
    collect_logs: bool = False,
    model: ModelEvaluator | None = None,
    opponent_model: ModelEvaluator | None = None,
) -> dict:
    if matchups is None:
        matchups = MODEL_MATRIX if model is not None else DEFAULT_MATRIX
        if model is not None and opponent_model is not None:
            matchups = (*matchups, ("model", "model"))

    results: list[dict] = []
    matrix: dict[str, dict] = {}
    for index, (ai_difficulty, opponent_difficulty) in enumerate(matchups):
        matchup_seed = seed + index * 1009
        result = evaluate(
            games=games,
            ai_difficulty=ai_difficulty,
            opponent_difficulty=opponent_difficulty,
            seed=matchup_seed,
            max_rounds=max_rounds,
            collect_logs=collect_logs,
            model=model,
            opponent_model=opponent_model,
        )
        key = (
            "model_vs_historical"
            if ai_difficulty == "model" and opponent_difficulty == "model"
            else f"{ai_difficulty}_vs_{opponent_difficulty}"
        )
        matrix[key] = {
            "win_rate": result["win_rate"],
            "loss_rate": result["loss_rate"],
            "draw_rate": result["draw_rate"],
            "double_lose_rate": result["double_lose_rate"],
            "truncated_rate": result["truncated_rate"],
            "average_rounds": result["average_rounds"],
            "illegal_moves": result["illegal_moves"],
            "fallback_count": result["fallback_count"],
            "fallback_rate": result["fallback_rate"],
            "timeout_count": result["timeout_count"],
            "timeout_rate": result["timeout_rate"],
            "average_inference_ms": result["average_inference_ms"],
            "p95_inference_ms": result["p95_inference_ms"],
            "max_inference_ms": result["max_inference_ms"],
            "p1_win_rate": result["p1_win_rate"],
            "p2_win_rate": result["p2_win_rate"],
            "seat_win_rate_delta": result["seat_win_rate_delta"],
        }
        results.append(result)

    report: dict = {
        "report_type": "clapclap_ai_matrix",
        "games_per_matchup": games,
        "seed": seed,
        "max_rounds": max_rounds,
        "matrix": matrix,
        "results": results,
    }
    if model is not None:
        report["model_info"] = {
            "model_version": model.info.model_version,
            "manifest_path": model.info.manifest_path,
            "weights_path": model.info.weights_path,
            "algorithm": model.info.algorithm,
            "inference_adapter": model.info.inference_adapter,
            "training_timesteps": model.info.training_timesteps,
            "is_loaded": model.is_loaded,
            "load_error": model.info.load_error,
        }
        if opponent_model is not None:
            report["historical_model_info"] = {
                "model_version": opponent_model.info.model_version,
                "manifest_path": opponent_model.info.manifest_path,
                "is_loaded": opponent_model.is_loaded,
                "load_error": opponent_model.info.load_error,
            }
        # ── 晋级判定 ──
        from scripts.promote_ai_model import DEFAULT_THRESHOLDS, check_thresholds
        passed, failures = check_thresholds(report)
        report["passed_promotion"] = passed
        report["promotion_failures"] = failures
        report["promotion_thresholds"] = dict(DEFAULT_THRESHOLDS)
    return report


def format_summary(report: dict) -> str:
    if report.get("report_type") == "clapclap_ai_matrix":
        lines = ["matchup win loss draw trunc avg_rounds illegal p1 p2"]
        for key, item in report["matrix"].items():
            lines.append(
                f"{key} {item['win_rate']:.4f} {item['loss_rate']:.4f} "
                f"{item['draw_rate']:.4f} {item['truncated_rate']:.4f} "
                f"{item['average_rounds']:.2f} {item['illegal_moves']} "
                f"{item['p1_win_rate']:.4f} {item['p2_win_rate']:.4f}"
            )
        return "\n".join(lines)

    return (
        "matchup win loss draw trunc avg_rounds illegal p1 p2\n"
        f"{report['ai_difficulty']}_vs_{report['opponent_difficulty']} "
        f"{report['win_rate']:.4f} {report['loss_rate']:.4f} "
        f"{report['draw_rate']:.4f} {report['truncated_rate']:.4f} "
        f"{report['average_rounds']:.2f} {report['illegal_moves']} "
        f"{report['p1_win_rate']:.4f} {report['p2_win_rate']:.4f}"
    )


def enforce_thresholds(
    report: dict,
    *,
    min_win_rate: float | None,
    max_truncated_rate: float | None,
    max_seat_win_rate_delta: float | None = None,
    max_action_concentration: float | None = None,
    max_double_loss_rate: float | None = None,
) -> list[str]:
    failures: list[str] = []
    results = report.get("results", [report])
    for result in results:
        label = f"{result['ai_difficulty']}_vs_{result['opponent_difficulty']}"
        if result["illegal_moves"] != 0:
            failures.append(f"{label}: illegal_moves={result['illegal_moves']}")
        if min_win_rate is not None and result["win_rate"] < min_win_rate:
            failures.append(f"{label}: win_rate={result['win_rate']} < {min_win_rate}")
        if max_truncated_rate is not None and result["truncated_rate"] > max_truncated_rate:
            failures.append(
                f"{label}: truncated_rate={result['truncated_rate']} > {max_truncated_rate}"
            )
        # P1/P2 胜率差
        if max_seat_win_rate_delta is not None:
            delta = result.get("seat_win_rate_delta", abs(
                result.get("p1_win_rate", 0) - result.get("p2_win_rate", 0)
            ))
            if delta > max_seat_win_rate_delta:
                failures.append(
                    f"{label}: seat_win_rate_delta={delta:.4f} > {max_seat_win_rate_delta}"
                )
        # 双败率
        if max_double_loss_rate is not None:
            dlr = result.get("double_lose_rate", result.get("draw_rate", 0))
            if dlr > max_double_loss_rate:
                failures.append(
                    f"{label}: double_lose_rate={dlr:.4f} > {max_double_loss_rate}"
                )
        # 动作分布极端坍缩
        if max_action_concentration is not None:
            action_counts = result.get("action_counts", {})
            if action_counts:
                total = sum(action_counts.values())
                max_ratio = max(action_counts.values()) / total if total > 0 else 0
                if max_ratio > max_action_concentration:
                    top_action = max(action_counts, key=action_counts.get)
                    failures.append(
                        f"{label}: action_concentration={max_ratio:.4f} "
                        f"(action={top_action}) > {max_action_concentration}"
                    )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ClapClap 1.0 AI policies.")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument(
        "--ai", choices=["easy", "normal", "hard", "random", "model"], default="normal"
    )
    parser.add_argument(
        "--opponent", choices=["easy", "normal", "hard", "random", "model"], default="easy"
    )
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Run the default evaluation matrix (or model matrix if --model-dir is set).",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        help="Evaluate a trained model (directory containing manifest.json + weights).",
    )
    parser.add_argument(
        "--opponent-model-dir",
        type=Path,
        help="Optional historical model used for candidate-vs-historical evaluation.",
    )
    parser.add_argument("--output", type=Path, help="Write JSON report to this path.")
    parser.add_argument(
        "--log-games", type=Path, help="Write detailed game logs as JSONL."
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print a compact table instead of JSON."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and model loadability without running games.",
    )
    parser.add_argument("--min-win-rate", type=float)
    parser.add_argument("--max-truncated-rate", type=float)
    parser.add_argument("--max-seat-delta", type=float)
    parser.add_argument("--max-action-concentration", type=float)
    parser.add_argument("--max-double-loss-rate", type=float)
    args = parser.parse_args()

    if args.games <= 0:
        raise SystemExit("--games must be greater than 0")
    if args.max_rounds <= 0:
        raise SystemExit("--max-rounds must be greater than 0")

    # ── 模型加载 ──────────────────────────────────────────────
    model: ModelEvaluator | None = None
    if args.model_dir:
        model = ModelEvaluator(args.model_dir.resolve(), max_rounds=args.max_rounds)
        if model.is_loaded:
            print(
                f"[model] 已加载: version={model.info.model_version}, "
                f"adapter={model.info.inference_adapter}"
            )
        else:
            print(f"[model] 加载失败: {model.info.load_error}，将回退 heuristic hard")

    opponent_model: ModelEvaluator | None = None
    if args.opponent_model_dir:
        opponent_model = ModelEvaluator(
            args.opponent_model_dir.resolve(), max_rounds=args.max_rounds
        )
        if not opponent_model.is_loaded:
            raise SystemExit(
                f"历史模型加载失败: {opponent_model.info.load_error}"
            )

    # ── dry-run ───────────────────────────────────────────────
    if args.dry_run:
        matchups = MODEL_MATRIX if model is not None else DEFAULT_MATRIX
        if model is not None and opponent_model is not None:
            matchups = (*matchups, ("model", "model"))
        total_games = len(matchups) * args.games if args.matrix else args.games
        dry_report: dict = {
            "report_type": "clapclap_ai_dry_run",
            "matrix_mode": args.matrix,
            "games": args.games,
            "seed": args.seed,
            "max_rounds": args.max_rounds,
            "matchups": [
                {"ai": ai, "opponent": opp}
                for ai, opp in (matchups if args.matrix else [(args.ai, args.opponent)])
            ],
            "total_matchups": len(matchups) if args.matrix else 1,
            "total_games": total_games,
            "estimated_time_minutes": round(total_games * 0.05 / 60, 1),
        }
        if model is not None:
            dry_report["model"] = {
                "model_dir": str(args.model_dir.resolve()),
                "is_loaded": model.is_loaded,
                "model_version": model.info.model_version,
                "load_error": model.info.load_error,
            }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(dry_report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[dry-run] 报告已写入: {args.output}")
        else:
            print(json.dumps(dry_report, ensure_ascii=False, indent=2))
        return

    # ── 评估 ─────────────────────────────────────────────────
    if args.matrix:
        report = evaluate_matrix(
            games=args.games,
            seed=args.seed,
            max_rounds=args.max_rounds,
            collect_logs=bool(args.log_games),
            model=model,
            opponent_model=opponent_model,
        )
    else:
        report = evaluate(
            games=args.games,
            ai_difficulty=args.ai,
            opponent_difficulty=args.opponent,
            seed=args.seed,
            max_rounds=args.max_rounds,
            collect_logs=bool(args.log_games),
            model=model,
            opponent_model=opponent_model,
        )

    if args.log_games:
        args.log_games.parent.mkdir(parents=True, exist_ok=True)
        results = report.get("results", [report])
        with args.log_games.open("w", encoding="utf-8") as fh:
            for result in results:
                for game_log in result.get("game_logs", []):
                    fh.write(json.dumps(game_log, ensure_ascii=False) + "\n")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    failures = enforce_thresholds(
        report,
        min_win_rate=args.min_win_rate,
        max_truncated_rate=args.max_truncated_rate,
        max_seat_win_rate_delta=args.max_seat_delta,
        max_action_concentration=args.max_action_concentration,
        max_double_loss_rate=args.max_double_loss_rate,
    )

    if args.summary:
        print(format_summary(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if failures:
        raise SystemExit("AI evaluation thresholds failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
