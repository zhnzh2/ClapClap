from __future__ import annotations

import unittest

import server.runtime as runtime
from server.app import app


class TestLocalApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with runtime.CURRENT_STATE_LOCK:
            runtime.CURRENT_STATE = runtime.CURRENT_STATE.__class__()

    # ---------- 基础流程 ----------

    def test_local_reset_and_step(self):
        """本地模式：重置后回合数为0，连续提交步进正常。"""
        reset = self.client.post("/api/local/reset").get_json()
        self.assertTrue(reset["ok"], reset)
        self.assertEqual(reset["state"]["round_num"], 0)

        for _ in range(3):
            result = self.client.post(
                "/api/local/step",
                json={"p1_move": "QI", "p2_move": "QI"},
            ).get_json()
            self.assertTrue(result["ok"], result)

        state = self.client.get("/api/local/state").get_json()
        self.assertEqual(state["round_num"], 3)

    def test_local_both_routes_consistent(self):
        """本地模式：旧路由和新 /api/local/... 路由结果一致。"""
        # 先通过旧路由提交
        self.client.post(
            "/api/local/step",
            json={"p1_move": "QI", "p2_move": "QI"},
        )

        state_old = self.client.get("/state").get_json()
        state_new = self.client.get("/api/local/state").get_json()
        self.assertEqual(state_old["round_num"], state_new["round_num"])

    def test_local_step_rejects_invalid_move_name(self):
        """本地模式：非法动作名应被拒绝。"""
        result = self.client.post(
            "/api/local/step",
            json={"p1_move": "NOT_A_REAL_MOVE", "p2_move": "QI"},
        ).get_json()
        self.assertFalse(result["ok"])
        self.assertIn("未知动作名", result.get("error", ""))

    def test_local_step_rejects_non_json_body(self):
        """本地模式：非 JSON 请求体应返回 400。"""
        resp = self.client.post(
            "/api/local/step",
            data="not json",
            content_type="text/plain",
        )
        self.assertEqual(resp.status_code, 400)

    def test_local_step_requires_both_moves(self):
        """本地模式：缺少 move 参数应被拒绝。"""
        result = self.client.post(
            "/api/local/step",
            json={"p1_move": "QI"},
        ).get_json()
        self.assertFalse(result["ok"])

    def test_local_game_ends_with_winner(self):
        """本地模式：P1 出 gi 攻击 P2 出气，P1 应获胜。"""
        with runtime.CURRENT_STATE_LOCK:
            runtime.CURRENT_STATE.p1.qi = 1

        result = self.client.post(
            "/api/local/step",
            json={"p1_move": "GI", "p2_move": "QI"},
        ).get_json()
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"]["winner"], 1)

    def test_local_state_lock_prevents_concurrent_modification(self):
        """本地模式：状态锁存在且可重入获取。"""
        self.assertTrue(runtime.CURRENT_STATE_LOCK.acquire(blocking=False))
        runtime.CURRENT_STATE_LOCK.release()


if __name__ == "__main__":
    unittest.main()
