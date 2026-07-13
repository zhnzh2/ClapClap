from __future__ import annotations

import unittest
from uuid import uuid4

from app import users
import server.runtime as runtime
from server.app import app


class TestLocalApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.user_ids = []
        self.headers = self._create_user_headers("local-a")
        self.second_headers = self._create_user_headers("local-b")

    def tearDown(self):
        for uid in self.user_ids:
            users.delete_user(uid)

    def _create_user_headers(self, prefix):
        username = f"{prefix}-{uuid4().hex[:8]}"
        registered = users.register(username, "test1234", verified="1")
        self.assertTrue(registered["ok"], registered)
        self.user_ids.append(registered["user"]["uid"])
        logged_in = users.login(username, "test1234")
        self.assertTrue(logged_in["ok"], logged_in)
        return {"X-Session-Token": logged_in["session_token"]}

    def _session(self):
        user = users.get_user_by_session_token(self.headers["X-Session-Token"])
        session_key = runtime.get_local_session_key(user)
        return runtime.get_local_session(session_key)

    # ---------- 基础流程 ----------

    def test_local_reset_and_step(self):
        """本地模式：重置后回合数为0，连续提交步进正常。"""
        reset = self.client.post("/v1/api/local/reset", headers=self.headers).get_json()
        self.assertTrue(reset["ok"], reset)
        self.assertEqual(reset["state"]["round_num"], 0)

        for _ in range(3):
            result = self.client.post(
                "/v1/api/local/step",
                json={"p1_move": "QI", "p2_move": "QI"},
                headers=self.headers,
            ).get_json()
            self.assertTrue(result["ok"], result)

        state = self.client.get("/v1/api/local/state", headers=self.headers).get_json()
        self.assertEqual(state["round_num"], 3)

    def test_local_api_state_reflects_step(self):
        """本地模式：/v1/api/local/... 路由提交后状态一致。"""
        self.client.post(
            "/v1/api/local/step",
            json={"p1_move": "QI", "p2_move": "QI"},
            headers=self.headers,
        )

        state = self.client.get("/v1/api/local/state", headers=self.headers).get_json()
        self.assertEqual(state["round_num"], 1)

    def test_local_step_rejects_invalid_move_name(self):
        """本地模式：非法动作名应被拒绝。"""
        result = self.client.post(
            "/v1/api/local/step",
            json={"p1_move": "NOT_A_REAL_MOVE", "p2_move": "QI"},
            headers=self.headers,
        ).get_json()
        self.assertFalse(result["ok"])
        self.assertIn("未知动作名", result.get("error", ""))

    def test_local_step_rejects_non_json_body(self):
        """本地模式：非 JSON 请求体应返回 400。"""
        resp = self.client.post(
            "/v1/api/local/step",
            data="not json",
            content_type="text/plain",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_local_step_requires_both_moves(self):
        """本地模式：缺少 move 参数应被拒绝。"""
        result = self.client.post(
            "/v1/api/local/step",
            json={"p1_move": "QI"},
            headers=self.headers,
        ).get_json()
        self.assertFalse(result["ok"])

    def test_local_game_ends_with_winner(self):
        """本地模式：P1 出 gi 攻击 P2 出气，P1 应获胜。"""
        with runtime.CURRENT_STATE_LOCK:
            self._session().state.p1.qi = 1

        result = self.client.post(
            "/v1/api/local/step",
            json={"p1_move": "GI", "p2_move": "QI"},
            headers=self.headers,
        ).get_json()
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["winner"], 1)

    def test_local_state_lock_prevents_concurrent_modification(self):
        """本地模式：状态锁存在且可重入获取。"""
        self.assertTrue(runtime.CURRENT_STATE_LOCK.acquire(blocking=False))
        runtime.CURRENT_STATE_LOCK.release()

    def test_local_api_requires_authentication(self):
        """本地模式接口必须拒绝未登录访问。"""
        self.assertEqual(self.client.get("/v1/api/local/state").status_code, 401)
        self.assertEqual(self.client.post("/v1/api/local/reset").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/v1/api/local/step",
                json={"p1_move": "QI", "p2_move": "QI"},
            ).status_code,
            401,
        )

    def test_local_state_is_isolated_per_user(self):
        """两个登录用户不能读取或推进彼此的本地对局。"""
        self.client.post("/v1/api/local/reset", headers=self.headers)
        self.client.post(
            "/v1/api/local/step",
            json={"p1_move": "QI", "p2_move": "QI"},
            headers=self.headers,
        )

        first = self.client.get("/v1/api/local/state", headers=self.headers).get_json()
        second = self.client.get("/v1/api/local/state", headers=self.second_headers).get_json()
        self.assertEqual(first["round_num"], 1)
        self.assertEqual(second["round_num"], 0)


if __name__ == "__main__":
    unittest.main()
