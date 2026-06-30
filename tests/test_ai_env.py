from __future__ import annotations

import random
import unittest

from app.ai_env import ClapClapEnv, action_index
from app.v1.constants import Move
from app.v1.models import GameState
from scripts.evaluate_ai import (
    enforce_thresholds,
    evaluate,
    evaluate_matrix,
    format_summary,
)


class TestClapClapEnv(unittest.TestCase):
    def test_reset_returns_observation_with_mask(self):
        env = ClapClapEnv(seed=1)
        obs = env.reset()

        self.assertEqual(obs["version"], env.observation_version)
        self.assertEqual(obs["ai_player"], 1)
        self.assertEqual(obs["round_num"], 0)
        self.assertEqual(len(obs["legal_action_mask"]), 17)
        self.assertTrue(obs["legal_action_mask"][action_index(Move.QI)])

    def test_step_uses_resolve_round_and_advances_state(self):
        def opponent_qi(state: GameState, player: int, rng: random.Random):
            return Move.QI

        env = ClapClapEnv(opponent_policy=opponent_qi, seed=1)
        result = env.step(action_index(Move.QI))

        self.assertFalse(result.terminated)
        self.assertFalse(result.truncated)
        self.assertEqual(env.state.round_num, 1)
        self.assertEqual(env.state.p1.qi, 1)
        self.assertEqual(env.state.p2.qi, 1)
        self.assertEqual(result.reward, 0.0)

    def test_illegal_action_raises(self):
        env = ClapClapEnv(seed=1)
        with self.assertRaises(ValueError):
            env.step(action_index(Move.GI))

    def test_terminal_reward(self):
        def opponent_qi(state: GameState, player: int, rng: random.Random):
            return Move.QI

        env = ClapClapEnv(opponent_policy=opponent_qi, seed=1)
        env.state.p1.qi = 1
        result = env.step(action_index(Move.GI))

        self.assertTrue(result.terminated)
        self.assertEqual(result.reward, 1.0)
        self.assertEqual(result.info["winner"], 1)


class TestEvaluateAi(unittest.TestCase):
    def test_evaluate_returns_core_metrics(self):
        result = evaluate(
            games=4,
            ai_difficulty="normal",
            opponent_difficulty="easy",
            seed=123,
            max_rounds=60,
        )

        self.assertEqual(result["games"], 4)
        self.assertIn("win_rate", result)
        self.assertIn("loss_rate", result)
        self.assertIn("draw_rate", result)
        self.assertIn("truncated_rate", result)
        self.assertIn("average_rounds", result)
        self.assertIn("action_counts", result)
        self.assertIn("average_inference_ms", result)
        self.assertEqual(result["illegal_moves"], 0)
        self.assertEqual(result["ai_as_p1_games"], 2)
        self.assertEqual(result["ai_as_p2_games"], 2)

    def test_evaluate_rejects_invalid_games(self):
        with self.assertRaises(ValueError):
            evaluate(
                games=0,
                ai_difficulty="normal",
                opponent_difficulty="easy",
                seed=123,
                max_rounds=60,
            )

    def test_evaluate_matrix_returns_default_matchups(self):
        report = evaluate_matrix(games=2, seed=123, max_rounds=40)

        self.assertEqual(report["report_type"], "clapclap_ai_matrix")
        self.assertEqual(report["games_per_matchup"], 2)
        self.assertIn("normal_vs_easy", report["matrix"])
        self.assertEqual(len(report["results"]), 5)
        self.assertIn("illegal_moves", report["matrix"]["normal_vs_easy"])

    def test_format_summary_for_matrix(self):
        report = evaluate_matrix(games=2, seed=123, max_rounds=40)
        summary = format_summary(report)

        self.assertIn("matchup win loss draw", summary)
        self.assertIn("normal_vs_easy", summary)

    def test_enforce_thresholds_reports_illegal_moves(self):
        failures = enforce_thresholds(
            {
                "ai_difficulty": "normal",
                "opponent_difficulty": "easy",
                "illegal_moves": 1,
                "win_rate": 1.0,
                "truncated_rate": 0.0,
            },
            min_win_rate=0.5,
            max_truncated_rate=0.2,
        )

        self.assertTrue(failures)

    def test_evaluate_can_collect_game_logs(self):
        result = evaluate(
            games=1,
            ai_difficulty="normal",
            opponent_difficulty="easy",
            seed=123,
            max_rounds=40,
            collect_logs=True,
        )

        self.assertIn("game_logs", result)
        self.assertEqual(len(result["game_logs"]), 1)
        first_game = result["game_logs"][0]
        self.assertIn("rounds_log", first_game)
        self.assertTrue(first_game["rounds_log"])
        first_round = first_game["rounds_log"][0]
        self.assertIn("round_start_state", first_round)
        self.assertIn("ai_legal_actions", first_round)
        self.assertIn("ai_move", first_round)
        self.assertIn("round_end_state", first_round)


if __name__ == "__main__":
    unittest.main()
