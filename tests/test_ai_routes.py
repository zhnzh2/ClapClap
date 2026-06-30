"""
阶段 3 测试：AI API 端点。

覆盖:
  - GET  /api/ai/state 与 /v1/api/ai/state
  - POST /api/ai/reset 与 /v1/api/ai/reset
  - POST /api/ai/step 与 /v1/api/ai/step（正常流程、错误处理、边界条件）
"""

from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from app import battle_recorder, users
from app.ai.space import ACTION_SPACE_SIZE, get_action_space_fingerprint
from app.v1.constants import Move
from app.v1.game import GameEngine
from server.app import app
import server.runtime as runtime


class TestAiApi(unittest.TestCase):
    """6.5 API 测试"""

    @classmethod
    def setUpClass(cls):
        # 注册一个测试专用用户，整个测试类共用
        unique = f"ai-tester-{uuid4().hex[:8]}"
        reg = users.register(unique, "test1234", verified="1")
        if reg["ok"]:
            cls._test_uid = reg["user"]["uid"]
            cls._test_username = unique
            login = users.login(unique, "test1234")
            cls._token = login.get("session_token", "")
        else:
            cls._test_uid = -1
            cls._token = ""

        second_unique = f"ai-tester-{uuid4().hex[:8]}"
        second_reg = users.register(second_unique, "test1234", verified="1")
        if second_reg["ok"]:
            cls._second_uid = second_reg["user"]["uid"]
            cls._second_username = second_unique
            second_login = users.login(second_unique, "test1234")
            cls._second_token = second_login.get("session_token", "")
        else:
            cls._second_uid = -1
            cls._second_username = ""
            cls._second_token = ""

    @classmethod
    def tearDownClass(cls):
        # 清理测试用户
        if cls._test_uid >= 0:
            users.delete_user(cls._test_uid)
        if cls._second_uid >= 0:
            users.delete_user(cls._second_uid)

    def setUp(self):
        self.client = app.test_client()
        self.headers = {"X-Session-Token": self._token}
        self.second_headers = {"X-Session-Token": self._second_token}
        # 每个测试前重置 AI session store
        with runtime.AI_STATE_LOCK:
            runtime.clear_ai_sessions()

    def _current_ai_session(self):
        session_key = runtime.get_ai_session_key(
            {"uid": self._test_uid, "username": self._test_username}
        )
        return runtime.get_ai_session(session_key)

    # ------------------------------------------------------------------
    # GET /api/ai/state
    # ------------------------------------------------------------------

    def test_get_state_returns_valid_payload(self):
        """获取 AI 对战状态。"""
        resp = self.client.get("/api/ai/state", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["round_num"], 0)
        self.assertIsNone(data["winner"])
        self.assertIsNone(data["battle_id"])
        self.assertIn("p1", data)
        self.assertIn("p2", data)
        self.assertIn("legal_moves", data)
        self.assertIn("move_catalog", data)

    def test_get_state_unauthorized(self):
        """未登录请求应返回 401。"""
        resp = self.client.get("/api/ai/state")
        self.assertEqual(resp.status_code, 401)

    # ------------------------------------------------------------------
    # POST /api/ai/reset
    # ------------------------------------------------------------------

    def test_reset_returns_valid_response(self):
        """重置 AI 对战。"""
        resp = self.client.post("/api/ai/reset", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["state"]["round_num"], 0)
        self.assertIsNone(data["state"]["battle_id"])

    def test_reset_clears_rounds(self):
        """重置后回合数归零。"""
        # 先打一回合
        self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        )
        # 重置
        resp = self.client.post("/api/ai/reset", headers=self.headers)
        data = resp.get_json()
        self.assertEqual(data["state"]["round_num"], 0)
        self.assertIsNone(data["state"]["winner"])
        self.assertIsNone(data["state"]["battle_id"])

    # ------------------------------------------------------------------
    # POST /api/ai/step — 正常流程
    # ------------------------------------------------------------------

    def test_step_returns_ai_move(self):
        """step 响应必须包含 ai_move。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"], data)
        self.assertIn("ai_move", data)
        self.assertIn("ai_move_label", data)
        self.assertIn("difficulty", data)
        self.assertIn("battle_id", data)
        self.assertEqual(data["battle_id"], data["state"]["battle_id"])
        self.assertIsInstance(data["battle_id"], str)
        self.assertEqual(data["human_seat"], "p1")
        self.assertEqual(data["ai_seat"], "p2")
        self.assertEqual(data["difficulty"], "easy")

    def test_v1_api_aliases_work(self):
        """AI API 同时提供 /v1/api/ai/* 版本化路径。"""
        state = self.client.get("/v1/api/ai/state", headers=self.headers)
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.get_json()["round_num"], 0)

        reset = self.client.post("/v1/api/ai/reset", headers=self.headers)
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.get_json()["ok"])

        step = self.client.post(
            "/v1/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        )
        self.assertEqual(step.status_code, 200)
        data = step.get_json()
        self.assertTrue(data["ok"], data)
        self.assertEqual(data["human_seat"], "p1")
        self.assertEqual(data["ai_seat"], "p2")
        battle_recorder.delete_battle(data["battle_id"])

    def test_step_round_increments(self):
        """每步后 round_num 递增。"""
        with patch("server.routes.ai_routes.select_move", return_value=Move.QI):
            for expected_round in range(1, 4):
                resp = self.client.post(
                    "/api/ai/step",
                    json={"human_move": "QI", "difficulty": "easy"},
                    headers=self.headers,
                )
                data = resp.get_json()
                self.assertTrue(data["ok"], data)
                self.assertEqual(data["state"]["round_num"], expected_round)

    def test_step_ai_move_is_legal(self):
        """AI 返回的动作不会导致非法判负（即 AI 动作对其座位合法）。"""
        for _ in range(30):
            resp = self.client.post(
                "/api/ai/step",
                json={"human_move": "QI", "difficulty": "easy"},
                headers=self.headers,
            )
            data = resp.get_json()
            self.assertTrue(data["ok"], data)

            # 如果 AI（P2）动作非法，resolve_round 会判 P1 获胜
            # 即 winner=1 且 p2_valid=False
            # 检查最新回合记录
            history = data["state"].get("history", [])
            if history:
                last_round = history[-1]
                # AI 为 P2，p2_valid 应为 True
                self.assertTrue(
                    last_round.get("p2_valid", True),
                    f"AI 动作 {data['ai_move']} 被判定为非法"
                )

            # 如果对局结束，重置后继续
            if data["state"]["winner"] is not None:
                self.client.post("/api/ai/reset", headers=self.headers)

    def test_step_multiple_difficulties(self):
        """三种难度都能正常结算。"""
        for difficulty in ("easy", "normal", "hard"):
            self.client.post("/api/ai/reset", headers=self.headers)
            resp = self.client.post(
                "/api/ai/step",
                json={"human_move": "QI", "difficulty": difficulty},
                headers=self.headers,
            )
            data = resp.get_json()
            self.assertTrue(data["ok"], f"难度 {difficulty}: {data}")
            self.assertEqual(data["difficulty"], difficulty)

    def test_difficulty_is_locked_after_first_round(self):
        """同一局开始后不允许中途切换 AI 难度，保证记录元信息准确。"""
        first = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        ).get_json()
        self.assertTrue(first["ok"], first)

        second = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "normal"},
            headers=self.headers,
        )

        self.assertEqual(second.status_code, 400)
        self.assertIn("难度已锁定", second.get_json().get("error", ""))
        battle_recorder.delete_battle(first["battle_id"])

    def test_step_supports_human_seat_p2(self):
        """真人坐 P2 时，AI 应自动控制 P1 并正确记录座位。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy", "human_seat": "p2"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"], data)
        self.assertEqual(data["human_seat"], "p2")
        self.assertEqual(data["ai_seat"], "p1")

        battle = battle_recorder.read_battle(data["battle_id"])
        self.assertEqual(battle.get("ai_seat"), "p1")
        participants = battle.get("participants", {})
        self.assertEqual(participants["p1"]["username"], "ClapClap AI")
        self.assertEqual(participants["p2"]["username"], self._test_username)
        battle_recorder.delete_battle(data["battle_id"])

    def test_state_exposes_existing_battle_id(self):
        """首次 step 后 state 接口应返回同一个 AI battle_id。"""
        step = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        ).get_json()
        battle_id = step["battle_id"]

        state = self.client.get("/api/ai/state", headers=self.headers).get_json()
        self.assertEqual(state["battle_id"], battle_id)

        battle_recorder.delete_battle(battle_id)

    def test_ai_decision_receives_round_start_state_only(self):
        """路由层防作弊：AI 只接收真人动作结算前的状态副本。"""
        seen_states = []

        def fake_select_move(state, controlled_player, rng, config):
            seen_states.append(state.copy())
            return Move.QI

        with patch("server.routes.ai_routes.select_move", side_effect=fake_select_move):
            first = self.client.post(
                "/api/ai/step",
                json={"human_move": "QI", "difficulty": "easy"},
                headers=self.headers,
            ).get_json()
        battle_recorder.delete_battle(first["battle_id"])

        self.client.post("/api/ai/reset", headers=self.headers)

        with patch("server.routes.ai_routes.select_move", side_effect=fake_select_move):
            second = self.client.post(
                "/api/ai/step",
                json={"human_move": "SHIELD", "difficulty": "easy"},
                headers=self.headers,
            ).get_json()
        battle_recorder.delete_battle(second["battle_id"])

        self.assertEqual(len(seen_states), 2)
        self.assertEqual(seen_states[0].round_num, 0)
        self.assertEqual(seen_states[1].round_num, 0)
        self.assertEqual(seen_states[0].p1.to_dict(), seen_states[1].p1.to_dict())
        self.assertEqual(seen_states[0].p2.to_dict(), seen_states[1].p2.to_dict())

    def test_step_game_ends_properly(self):
        """
        连续出招直到终局，验证 API 正确处理终局。

        AI 为 P2，真人 P1 一直出 QI。AI 可能随机获胜、失败或双败。
        不管结果如何，游戏结束后应不能再提交。
        """
        max_steps = 200
        for _ in range(max_steps):
            resp = self.client.post(
                "/api/ai/step",
                json={"human_move": "QI", "difficulty": "easy"},
                headers=self.headers,
            )
            data = resp.get_json()
            if not data["ok"]:
                # 可能是游戏已结束
                self.assertIn("结束", data.get("error", ""))
                break

            state = data["state"]
            if state["winner"] is not None:
                # 游戏结束，再提交应报错
                resp2 = self.client.post(
                    "/api/ai/step",
                    json={"human_move": "QI", "difficulty": "easy"},
                    headers=self.headers,
                )
                data2 = resp2.get_json()
                self.assertFalse(data2["ok"])
                self.assertEqual(resp2.status_code, 400)
                break
        else:
            self.fail(f"对局在 {max_steps} 回合内未结束")

    # ------------------------------------------------------------------
    # POST /api/ai/step — 错误处理
    # ------------------------------------------------------------------

    def test_step_non_json_returns_400(self):
        """非 JSON 请求返回 400。"""
        resp = self.client.post(
            "/api/ai/step",
            data="not json",
            content_type="text/plain",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_step_missing_human_move_returns_400(self):
        """缺少 human_move 返回 400。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"difficulty": "easy"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["ok"])

    def test_step_invalid_move_returns_400(self):
        """非法动作名返回 400。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "NONEXISTENT", "difficulty": "easy"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_step_illegal_move_returns_400(self):
        """对当前玩家不合法的动作返回 400。"""
        # 初始 qi=0，GI 不合法
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "GI", "difficulty": "easy"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("不合法", data.get("error", ""))

    def test_step_unknown_difficulty_returns_400(self):
        """未知难度返回 400。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "impossible"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_step_after_game_over_returns_400(self):
        """游戏结束后继续提交返回 400。"""
        # 强制设 winner 模拟终局
        with runtime.AI_STATE_LOCK:
            self._current_ai_session().state.winner = 1

        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("结束", data.get("error", ""))

    def test_step_invalid_human_seat_returns_400(self):
        """无效 human_seat 返回 400。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "human_seat": "p3"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # 状态隔离测试
    # ------------------------------------------------------------------

    def test_ai_state_independent_from_local(self):
        """AI_STATE 与 CURRENT_STATE（本地模式）互不影响。"""
        # 操作 AI 状态
        self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        )
        ai_state = self.client.get("/api/ai/state", headers=self.headers).get_json()

        # 本地模式状态应保持初始
        local_state = self.client.get("/v1/api/local/state").get_json()

        self.assertNotEqual(ai_state["round_num"], local_state["round_num"],
                            "AI 状态和本地模式状态应独立")

    def test_ai_state_isolated_per_user(self):
        """不同登录用户的 AI 对局状态互不影响。"""
        first_step = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        ).get_json()
        self.assertTrue(first_step["ok"], first_step)

        first_state = self.client.get("/api/ai/state", headers=self.headers).get_json()
        second_state = self.client.get(
            "/api/ai/state", headers=self.second_headers
        ).get_json()

        self.assertEqual(first_state["round_num"], 1)
        self.assertIsInstance(first_state["battle_id"], str)
        self.assertEqual(second_state["round_num"], 0)
        self.assertIsNone(second_state["battle_id"])

        battle_recorder.delete_battle(first_state["battle_id"])

    def test_ai_reset_only_resets_current_user(self):
        """用户 A reset 不会清掉用户 B 的 AI 对局。"""
        first = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        ).get_json()
        second = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.second_headers,
        ).get_json()
        self.assertTrue(first["ok"], first)
        self.assertTrue(second["ok"], second)

        self.client.post("/api/ai/reset", headers=self.headers)

        first_state = self.client.get("/api/ai/state", headers=self.headers).get_json()
        second_state = self.client.get(
            "/api/ai/state", headers=self.second_headers
        ).get_json()

        self.assertEqual(first_state["round_num"], 0)
        self.assertIsNone(first_state["battle_id"])
        self.assertEqual(second_state["round_num"], 1)
        self.assertEqual(second_state["battle_id"], second["battle_id"])

        battle_recorder.delete_battle(first["battle_id"])
        battle_recorder.delete_battle(second["battle_id"])

    # ------------------------------------------------------------------
    # 对战记录验证
    # ------------------------------------------------------------------

    def test_step_creates_battle_record(self):
        """step 应创建对战记录，且包含 AI 元信息。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "normal"},
            headers=self.headers,
        )
        data = resp.get_json()
        self.assertTrue(data["ok"])

        # 检查当前用户 session 中有 battle_id
        with runtime.AI_STATE_LOCK:
            battle_id = self._current_ai_session().battle_id

        self.assertIsNotNone(battle_id)

        # 读取对战记录验证
        battle = battle_recorder.read_battle(battle_id)
        self.assertIsNotNone(battle, f"对战记录 {battle_id} 不存在")
        self.assertEqual(battle.get("opponent_type"), "ai")
        self.assertEqual(battle.get("ai_difficulty"), "normal")
        self.assertEqual(battle.get("ai_seat"), "p2")  # 默认真人 P1, AI P2
        self.assertEqual(battle.get("human_seat"), "p1")
        self.assertEqual(battle.get("ai_policy_type"), "heuristic")
        self.assertIsNone(battle.get("ai_model_version"))
        self.assertEqual(battle.get("action_space_size"), ACTION_SPACE_SIZE)
        self.assertEqual(
            battle.get("action_space_fingerprint"),
            get_action_space_fingerprint(),
        )
        self.assertEqual(
            battle.get("observation_version"),
            "clapclap-v1-public-state-v1",
        )
        self.assertEqual(battle.get("rule_version"), "1.0")
        self.assertEqual(battle.get("mode"), "ai")
        self.assertEqual(len(battle.get("rounds", [])), 1)
        latest_round = battle.get("rounds", [])[0]
        self.assertEqual(latest_round.get("human_seat"), "p1")
        self.assertEqual(latest_round.get("ai_seat"), "p2")
        self.assertEqual(latest_round.get("ai_difficulty"), "normal")
        self.assertEqual(latest_round.get("ai_policy_type"), "heuristic")
        self.assertEqual(latest_round.get("ai_move"), data["ai_move"])
        self.assertEqual(latest_round.get("human_move"), "QI")

        # 清理
        battle_recorder.delete_battle(battle_id)

    def test_battle_participants_have_ai_p2(self):
        """对战记录参与者中 P2 为 ClapClap AI（uid=-2）。"""
        resp = self.client.post(
            "/api/ai/step",
            json={"human_move": "QI", "difficulty": "easy"},
            headers=self.headers,
        )
        data = resp.get_json()
        self.assertTrue(data["ok"])

        with runtime.AI_STATE_LOCK:
            battle_id = self._current_ai_session().battle_id

        battle = battle_recorder.read_battle(battle_id)
        participants = battle.get("participants", {})
        self.assertEqual(participants["p2"]["username"], "ClapClap AI")
        self.assertEqual(participants["p2"]["uid"], -2)

        battle_recorder.delete_battle(battle_id)


if __name__ == "__main__":
    unittest.main()
