from __future__ import annotations

import unittest

from app import matchmaking
from app.matchmaking import (
    MATCH_LOCK,
    PLAYER_MATCH_STATE,
    cancel_match,
    enqueue_or_match,
    get_match_status,
    get_player_match_state,
    load_match_state,
    persist_match_state,
)
from app.room_manager import delete_room_by_id
from app.storage import delete_kv
from server.app import app
from server.extensions import socketio

class TestMatchmaking(unittest.TestCase):
    def setUp(self):
        self.created_room_ids: list[str] = []
        with MATCH_LOCK:
            matchmaking.MATCH_WAITING = None
            PLAYER_MATCH_STATE.clear()
            delete_kv("match_state")

    def tearDown(self):
        for room_id in self.created_room_ids:
            delete_room_by_id(room_id)
        with MATCH_LOCK:
            matchmaking.MATCH_WAITING = None
            PLAYER_MATCH_STATE.clear()
            delete_kv("match_state")

    def test_enqueue_cancel_and_status(self):
        queued = enqueue_or_match("Alice", "match-a")
        self.assertFalse(queued["matched"])
        self.assertEqual(queued["waiting_player"], "Alice")
        self.assertTrue(get_match_status()["has_waiting_player"])

        cancelled = cancel_match("match-a")
        self.assertTrue(cancelled["ok"])
        self.assertTrue(cancelled["cancelled"])
        self.assertFalse(get_match_status()["has_waiting_player"])

    def test_pairing_creates_room_and_player_states(self):
        enqueue_or_match("Alice", "match-a")
        matched = enqueue_or_match("Bob", "match-b")
        self.assertTrue(matched["matched"], matched)
        self.assertEqual(matched["seat"], "p2")
        self.assertTrue(matched["room_player_token"])
        self.created_room_ids.append(matched["room_id"])

        alice_state = get_player_match_state("match-a")
        bob_state = get_player_match_state("match-b")

        self.assertEqual(alice_state["status"], "matched")
        self.assertEqual(alice_state["seat"], "p1")
        self.assertEqual(alice_state["opponent_name"], "Bob")
        self.assertTrue(alice_state["room_player_token"])

        self.assertEqual(bob_state["status"], "matched")
        self.assertEqual(bob_state["seat"], "p2")
        self.assertEqual(bob_state["opponent_name"], "Alice")
        self.assertEqual(bob_state["room_id"], matched["room_id"])

    def test_match_state_restores_from_storage(self):
        enqueue_or_match("Alice", "match-a")
        persist_match_state()

        with MATCH_LOCK:
            matchmaking.MATCH_WAITING = None
            PLAYER_MATCH_STATE.clear()

        load_match_state()

        self.assertTrue(get_match_status()["has_waiting_player"])
        self.assertEqual(get_match_status()["waiting_player"], "Alice")
        restored = get_player_match_state("match-a")
        self.assertEqual(restored["status"], "queued")
        self.assertEqual(restored["player_name"], "Alice")

    def test_match_lobby_socket_receives_status(self):
        client = socketio.test_client(app)
        try:
            client.emit("join_match_lobby")
            received = client.get_received()
            self.assertTrue(
                any(item["name"] == "match_status" for item in received),
                received,
            )
        finally:
            client.disconnect()

    def test_duplicate_enqueue_same_token(self):
        """测试同一 token 重复排队：第二次应返回 already_queued。"""
        first = enqueue_or_match("Alice", "match-a")
        self.assertFalse(first["matched"])
        self.assertTrue(first["already_queued"] is False)

        second = enqueue_or_match("Alice", "match-a")
        self.assertFalse(second["matched"])
        self.assertTrue(second["already_queued"])

    def test_already_matched_player_queues_again(self):
        """测试已匹配的玩家再次排队：应返回 already_in_room。"""
        enqueue_or_match("Alice", "match-a")
        matched = enqueue_or_match("Bob", "match-b")
        self.assertTrue(matched["matched"])
        self.created_room_ids.append(matched["room_id"])

        # Alice 已匹配，再次排队
        retry = enqueue_or_match("Alice", "match-a")
        self.assertTrue(retry["matched"])
        self.assertTrue(retry.get("already_in_room"))

    def test_self_match_prevented(self):
        """测试自己不能匹配自己。"""
        first = enqueue_or_match("Alice", "match-a")
        self.assertFalse(first["matched"])

        # 同一个 player_token 再次排队（在 MATCH_WAITING 中就是自己）
        second = enqueue_or_match("Alice", "match-a")
        self.assertFalse(second["matched"])
        self.assertTrue(second["already_queued"])

    def test_e2e_match_to_room_resolve(self):
        """端到端：匹配成功 → 进入房间 → 双方提交动作 → 结算回合。"""
        from app.room_manager import get_room

        # 1. 排队配对
        enqueue_or_match("Alice", "e2e-a")
        matched = enqueue_or_match("Bob", "e2e-b")
        self.assertTrue(matched["matched"], matched)
        room_id = matched["room_id"]
        self.created_room_ids.append(room_id)

        alice_state = get_player_match_state("e2e-a")
        bob_state = get_player_match_state("e2e-b")

        # 2. 验证双方在同一房间
        self.assertEqual(alice_state["room_id"], room_id)
        self.assertEqual(bob_state["room_id"], room_id)

        room = get_room(room_id)
        self.assertIsNotNone(room)
        self.assertEqual(room.status, "playing")

        # 3. 用 Flask test client 模拟双方提交动作
        from server.app import app as flask_app
        client = flask_app.test_client()

        # P1 (Alice) 提交
        p1_result = client.post(
            f"/api/rooms/{room_id}/step",
            json={
                "player_token": alice_state["room_player_token"],
                "move_name": "QI",
            },
        ).get_json()
        self.assertTrue(p1_result["ok"], p1_result)
        self.assertFalse(p1_result["resolved"])

        # P2 (Bob) 提交，触发结算
        p2_result = client.post(
            f"/api/rooms/{room_id}/step",
            json={
                "player_token": bob_state["room_player_token"],
                "move_name": "QI",
            },
        ).get_json()
        self.assertTrue(p2_result["ok"], p2_result)
        self.assertTrue(p2_result["resolved"])
        self.assertEqual(p2_result["room"]["game"]["round_num"], 1)

        # 4. 验证房间状态
        updated_room = get_room(room_id)
        self.assertEqual(updated_room.state.round_num, 1)
        self.assertEqual(len(updated_room.state.history), 1)


if __name__ == "__main__":
    unittest.main()
