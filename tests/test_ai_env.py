from __future__ import annotations

import random
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

from app.ai.space import ACTION_SPACE_SIZE, get_action_space_fingerprint
from app.ai_env import ClapClapEnv, action_index, validate_model_metadata
from app.ai.model_runtime import (
    clear_model_status_cache,
    get_model_status,
    policy_type_for_difficulty,
)
from app.v1.constants import Move
from app.v1.models import GameState
from scripts.evaluate_ai import (
    enforce_thresholds,
    evaluate,
    evaluate_matrix,
    format_summary,
)
from training.train_maskable_ppo import build_training_manifest
from training.gym_env import (
    ACTION_SPACE_SIZE as GYM_ACTION_SPACE_SIZE,
    OBSERVATION_VECTOR_SIZE,
    encode_observation_vector,
    make_gymnasium_env,
)


class TestClapClapEnv(unittest.TestCase):
    def test_reset_returns_observation_with_mask(self):
        env = ClapClapEnv(seed=1)
        obs = env.reset()

        self.assertEqual(obs["version"], env.observation_version)
        self.assertEqual(obs["metadata"]["rule_version"], "1.0")
        self.assertEqual(obs["metadata"]["action_space_size"], ACTION_SPACE_SIZE)
        self.assertEqual(
            obs["metadata"]["action_space_fingerprint"],
            get_action_space_fingerprint(),
        )
        self.assertEqual(
            obs["metadata"]["reward_config_version"],
            env.reward_config_version,
        )
        self.assertEqual(obs["ai_player"], 1)
        self.assertEqual(obs["round_num"], 0)
        self.assertEqual(len(obs["legal_action_mask"]), 17)
        self.assertTrue(obs["legal_action_mask"][action_index(Move.QI)])
        self.assertEqual(obs["history"], [])

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

    def test_history_window_is_trimmed(self):
        def opponent_qi(state: GameState, player: int, rng: random.Random):
            return Move.QI

        env = ClapClapEnv(opponent_policy=opponent_qi, seed=1, history_window=2)
        for _ in range(3):
            env.step(action_index(Move.QI))

        obs = env.encode_observation()
        self.assertEqual(len(obs["history"]), 2)
        self.assertEqual(obs["history"][0]["round_num"], 2)
        self.assertEqual(obs["history"][1]["round_num"], 3)

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
        self.assertEqual(result.info["reward_config_version"], env.reward_config_version)

    def test_observation_space_schema_is_versioned(self):
        env = ClapClapEnv(seed=1)
        schema = env.observation_space_schema()

        self.assertEqual(schema["version"], env.observation_version)
        self.assertIn("self", schema)
        self.assertIn("opponent", schema)
        self.assertIn("legal_action_mask", schema)

    def test_model_metadata_validation(self):
        env = ClapClapEnv(seed=1)
        metadata = env.metadata()

        self.assertTrue(validate_model_metadata(metadata))

        changed = dict(metadata)
        changed["action_space_fingerprint"] = "bad"
        self.assertFalse(validate_model_metadata(changed))

        changed = dict(metadata)
        changed["observation_version"] = "old"
        self.assertFalse(validate_model_metadata(changed))

    def test_training_manifest_uses_current_env_metadata(self):
        manifest = build_training_manifest(Namespace(
            dry_run=True,
            max_rounds=120,
            history_window=4,
            seed=20260630,
            total_timesteps=1000,
            model_version="dev",
        ))

        self.assertEqual(
            manifest["manifest_version"],
            "clapclap-ai-model-manifest-v1",
        )
        self.assertEqual(manifest["algorithm"], "MaskablePPO")
        self.assertEqual(manifest["model_version"], "dev")
        self.assertEqual(manifest["inference_adapter"], "sb3_maskable_ppo_v1")
        self.assertTrue(validate_model_metadata(manifest["env_metadata"]))
        self.assertTrue(manifest["training"]["seat_randomization"])

    def test_gym_observation_vector_shape(self):
        env = ClapClapEnv(seed=1)
        observation = env.reset()
        vector = encode_observation_vector(observation, max_rounds=env.max_rounds)

        self.assertEqual(len(vector), OBSERVATION_VECTOR_SIZE)
        self.assertEqual(GYM_ACTION_SPACE_SIZE, 17)
        self.assertEqual(vector[-17:], [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0])

    def test_gym_env_factory_requires_optional_dependencies(self):
        try:
            env = make_gymnasium_env(seed=1)
        except RuntimeError as exc:
            self.assertIn("Training dependencies are not installed", str(exc))
        else:
            observation, info = env.reset(seed=1)
            self.assertEqual(observation.shape[0], OBSERVATION_VECTOR_SIZE)
            self.assertIn("metadata", info)
            self.assertEqual(env.action_space.n, 17)

    def test_missing_production_model_falls_back_to_heuristic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"CLAPCLAP_AI_MODEL_DIR": tmpdir}):
                clear_model_status_cache()
                status = get_model_status()

                self.assertFalse(status.available)
                self.assertEqual(status.policy_type, "heuristic_fallback")
                self.assertEqual(policy_type_for_difficulty("hard"), "heuristic_fallback")


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

    def test_normal_has_stable_advantage_over_easy(self):
        result = evaluate(
            games=40,
            ai_difficulty="normal",
            opponent_difficulty="easy",
            seed=20260630,
            max_rounds=120,
        )

        self.assertEqual(result["illegal_moves"], 0)
        self.assertEqual(result["truncated"], 0)
        self.assertGreaterEqual(result["win_rate"], 0.85)
        self.assertLessEqual(result["seat_win_rate_delta"], 0.2)

    def test_hard_is_not_weaker_than_normal_baseline(self):
        result = evaluate(
            games=40,
            ai_difficulty="hard",
            opponent_difficulty="normal",
            seed=20260630,
            max_rounds=120,
        )

        self.assertEqual(result["illegal_moves"], 0)
        self.assertEqual(result["truncated"], 0)
        self.assertGreaterEqual(result["win_rate"], 0.9)
        self.assertLessEqual(result["seat_win_rate_delta"], 0.2)


if __name__ == "__main__":
    unittest.main()
