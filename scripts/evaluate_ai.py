from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai.engine import select_move
from app.v1.game import GameEngine
from app.v1.models import GameState

Difficulty = Literal["easy", "normal", "hard"]


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

    @property
    def win_rate(self) -> float:
        return round(self.ai_wins / self.games, 4) if self.games else 0.0

    @property
    def average_rounds(self) -> float:
        return round(self.total_rounds / self.games, 2) if self.games else 0.0


def _choose_move(state: GameState, player: int, difficulty: Difficulty, rng: random.Random):
    return select_move(state.copy(), player, rng, {"difficulty": difficulty})


def play_game(
    *,
    ai_difficulty: Difficulty,
    opponent_difficulty: Difficulty,
    ai_player: int,
    rng: random.Random,
    max_rounds: int,
) -> tuple[int | None, int, Counter, int]:
    state = GameState()
    action_counts: Counter = Counter()
    illegal_moves = 0

    while state.winner is None and state.round_num < max_rounds:
        round_start = state.copy()
        opponent_player = 2 if ai_player == 1 else 1

        ai_move = _choose_move(round_start, ai_player, ai_difficulty, rng)
        opponent_move = _choose_move(round_start, opponent_player, opponent_difficulty, rng)

        if ai_player == 1:
            p1_move, p2_move = ai_move, opponent_move
        else:
            p1_move, p2_move = opponent_move, ai_move

        GameEngine.resolve_round(state, p1_move, p2_move)
        action_counts[ai_move.name] += 1
        if state.history:
            latest = state.history[-1]
            if ai_player == 1 and not latest.p1_valid:
                illegal_moves += 1
            if ai_player == 2 and not latest.p2_valid:
                illegal_moves += 1

    return state.winner, state.round_num, action_counts, illegal_moves


def evaluate(
    *,
    games: int,
    ai_difficulty: Difficulty,
    opponent_difficulty: Difficulty,
    seed: int,
    max_rounds: int,
) -> dict:
    rng = random.Random(seed)
    result = EvaluationResult(
        games=games,
        ai_difficulty=ai_difficulty,
        opponent_difficulty=opponent_difficulty,
    )
    action_counts: Counter = Counter()

    for game_index in range(games):
        ai_player = 1 if game_index % 2 == 0 else 2
        if ai_player == 1:
            result.ai_as_p1_games += 1
        else:
            result.ai_as_p2_games += 1

        winner, rounds, counts, illegal = play_game(
            ai_difficulty=ai_difficulty,
            opponent_difficulty=opponent_difficulty,
            ai_player=ai_player,
            rng=rng,
            max_rounds=max_rounds,
        )
        result.total_rounds += rounds
        result.illegal_moves += illegal
        action_counts.update(counts)

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

    payload = asdict(result)
    payload["win_rate"] = result.win_rate
    payload["average_rounds"] = result.average_rounds
    payload["action_counts"] = dict(sorted(action_counts.items()))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ClapClap 1.0 AI policies.")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--ai", choices=["easy", "normal", "hard"], default="normal")
    parser.add_argument("--opponent", choices=["easy", "normal", "hard"], default="easy")
    parser.add_argument("--seed", type=int, default=20260629)
    parser.add_argument("--max-rounds", type=int, default=200)
    args = parser.parse_args()

    if args.games <= 0:
        raise SystemExit("--games must be greater than 0")

    result = evaluate(
        games=args.games,
        ai_difficulty=args.ai,
        opponent_difficulty=args.opponent,
        seed=args.seed,
        max_rounds=args.max_rounds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
