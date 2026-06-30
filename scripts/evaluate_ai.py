from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai.engine import get_legal_moves_list, select_move
from app.v1.game import GameEngine
from app.v1.models import GameState

Difficulty = Literal["easy", "normal", "hard"]
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "normal", "hard")
DEFAULT_MATRIX: tuple[tuple[Difficulty, Difficulty], ...] = (
    ("easy", "easy"),
    ("normal", "easy"),
    ("hard", "easy"),
    ("hard", "normal"),
    ("normal", "hard"),
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
    def average_inference_ms(self) -> float:
        if not self.inference_calls:
            return 0.0
        return round(self.total_inference_ms / self.inference_calls, 4)


def _choose_move(
    state: GameState,
    player: int,
    difficulty: Difficulty,
    rng: random.Random,
) -> tuple[object, float]:
    started = time.perf_counter()
    move = select_move(state.copy(), player, rng, {"difficulty": difficulty})
    elapsed_ms = (time.perf_counter() - started) * 1000
    return move, elapsed_ms


def _player_state(state: GameState, player: int):
    return state.p1 if player == 1 else state.p2


def play_game(
    *,
    ai_difficulty: Difficulty,
    opponent_difficulty: Difficulty,
    ai_player: int,
    rng: random.Random,
    max_rounds: int,
    collect_log: bool = False,
) -> dict:
    state = GameState()
    action_counts: Counter = Counter()
    illegal_moves = 0
    ai_flash_uses = 0
    ai_pickaxe_actions = 0
    inference_times_ms: list[float] = []
    rounds_log: list[dict] = []

    while state.winner is None and state.round_num < max_rounds:
        round_start = state.copy()
        opponent_player = 2 if ai_player == 1 else 1
        ai_legal = [move.name for move in get_legal_moves_list(round_start, ai_player)]
        opponent_legal = [
            move.name for move in get_legal_moves_list(round_start, opponent_player)
        ]

        ai_move, ai_elapsed_ms = _choose_move(round_start, ai_player, ai_difficulty, rng)
        opponent_move, _ = _choose_move(round_start, opponent_player, opponent_difficulty, rng)
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
        "rounds_log": rounds_log,
    }


def evaluate(
    *,
    games: int,
    ai_difficulty: Difficulty,
    opponent_difficulty: Difficulty,
    seed: int,
    max_rounds: int,
    collect_logs: bool = False,
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
        result.inference_calls += len(game["inference_times_ms"])
        result.total_inference_ms += sum(game["inference_times_ms"])
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
    payload["action_counts"] = dict(sorted(action_counts.items()))
    if collect_logs:
        payload["game_logs"] = game_logs
    return payload


def evaluate_matrix(
    *,
    games: int,
    seed: int,
    max_rounds: int,
    matchups: tuple[tuple[Difficulty, Difficulty], ...] = DEFAULT_MATRIX,
    collect_logs: bool = False,
) -> dict:
    results = []
    matrix = {}
    for index, (ai_difficulty, opponent_difficulty) in enumerate(matchups):
        matchup_seed = seed + index * 1009
        result = evaluate(
            games=games,
            ai_difficulty=ai_difficulty,
            opponent_difficulty=opponent_difficulty,
            seed=matchup_seed,
            max_rounds=max_rounds,
            collect_logs=collect_logs,
        )
        key = f"{ai_difficulty}_vs_{opponent_difficulty}"
        matrix[key] = {
            "win_rate": result["win_rate"],
            "loss_rate": result["loss_rate"],
            "draw_rate": result["draw_rate"],
            "truncated_rate": result["truncated_rate"],
            "average_rounds": result["average_rounds"],
            "illegal_moves": result["illegal_moves"],
            "p1_win_rate": result["p1_win_rate"],
            "p2_win_rate": result["p2_win_rate"],
        }
        results.append(result)
    return {
        "report_type": "clapclap_ai_matrix",
        "games_per_matchup": games,
        "seed": seed,
        "max_rounds": max_rounds,
        "matrix": matrix,
        "results": results,
    }


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
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ClapClap 1.0 AI policies.")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--ai", choices=["easy", "normal", "hard"], default="normal")
    parser.add_argument("--opponent", choices=["easy", "normal", "hard"], default="easy")
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--matrix", action="store_true", help="Run the default evaluation matrix.")
    parser.add_argument("--output", type=Path, help="Write JSON report to this path.")
    parser.add_argument("--log-games", type=Path, help="Write detailed game logs as JSONL.")
    parser.add_argument("--summary", action="store_true", help="Print a compact table instead of JSON.")
    parser.add_argument("--min-win-rate", type=float)
    parser.add_argument("--max-truncated-rate", type=float)
    args = parser.parse_args()

    if args.games <= 0:
        raise SystemExit("--games must be greater than 0")
    if args.max_rounds <= 0:
        raise SystemExit("--max-rounds must be greater than 0")

    if args.matrix:
        report = evaluate_matrix(
            games=args.games,
            seed=args.seed,
            max_rounds=args.max_rounds,
            collect_logs=bool(args.log_games),
        )
    else:
        report = evaluate(
            games=args.games,
            ai_difficulty=args.ai,
            opponent_difficulty=args.opponent,
            seed=args.seed,
            max_rounds=args.max_rounds,
            collect_logs=bool(args.log_games),
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
    )

    if args.summary:
        print(format_summary(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if failures:
        raise SystemExit("AI evaluation thresholds failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
