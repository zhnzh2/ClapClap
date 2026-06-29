from __future__ import annotations

import random
import unittest

from app.ai_env import ClapClapEnv, action_index
from app.v1.constants import Move
from app.v1.models import GameState
from scripts.evaluate_ai import evaluate


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
        self.assertIn("average_rounds", result)
        self.assertIn("action_counts", result)
        self.assertEqual(result["illegal_moves"], 0)
        self.assertEqual(result["ai_as_p1_games"], 2)
        self.assertEqual(result["ai_as_p2_games"], 2)


if __name__ == "__main__":
    unittest.main()
