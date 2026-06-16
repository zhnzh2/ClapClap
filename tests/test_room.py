from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from app.room_manager import (
    ROOMS,
    ROOM_RUNTIME_LOCKS,
    create_room,
    delete_room_by_id,
    get_room,
    get_room_runtime_lock,
)
import server.runtime as runtime
from server.app import app
from server.extensions import socketio

class TestRoomAndLocalApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.room_ids: list[str] = []

    def tearDown(self):
        for room_id in self.room_ids:
            delete_room_by_id(room_id)

    def create_joined_room(self):
        created = self.client.post(
            "/api/rooms",
            json={"player_name": "Alice"},
        ).get_json()
        self.assertTrue(created["ok"], created)
        room_id = created["room"]["room_id"]
        self.room_ids.append(room_id)

        joined = self.client.post(
            f"/api/rooms/{room_id}/join",
            json={"player_name": "Bob"},
        ).get_json()
        self.assertTrue(joined["ok"], joined)

        return room_id, created["player_token"], joined["player_token"]

    def test_local_api_uses_shared_state_safely(self):
        with runtime.CURRENT_STATE_LOCK:
            runtime.CURRENT_STATE = runtime.CURRENT_STATE.__class__()

        reset = self.client.post("/reset").get_json()
        self.assertTrue(reset["ok"], reset)
        self.assertEqual(reset["state"]["round_num"], 0)

        for _ in range(3):
            result = self.client.post(
                "/step",
                json={"p1_move": "QI", "p2_move": "QI"},
            ).get_json()
            self.assertTrue(result["ok"], result)

        state = self.client.get("/state").get_json()
        self.assertEqual(state["round_num"], 3)

        api_state = self.client.get("/api/local/state").get_json()
        self.assertEqual(api_state["round_num"], 3)

        api_step = self.client.post(
            "/api/local/step",
            json={"p1_move": "QI", "p2_move": "QI"},
        ).get_json()
        self.assertTrue(api_step["ok"], api_step)

    def test_room_create_join_submit_cancel_and_resolve(self):
        room_id, p1_token, p2_token = self.create_joined_room()

        first_submit = self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": p1_token, "move_name": "QI"},
        ).get_json()
        self.assertTrue(first_submit["ok"], first_submit)
        self.assertFalse(first_submit["resolved"])
        self.assertEqual(first_submit["room"]["pending_p1_move"], "QI")

        cancel = self.client.post(
            f"/api/rooms/{room_id}/cancel-step",
            json={"player_token": p1_token},
        ).get_json()
        self.assertTrue(cancel["ok"], cancel)
        self.assertIsNone(cancel["room"]["pending_p1_move"])

        self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": p1_token, "move_name": "QI"},
        )
        resolved = self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": p2_token, "move_name": "QI"},
        ).get_json()
        self.assertTrue(resolved["ok"], resolved)
        self.assertTrue(resolved["resolved"])
        self.assertEqual(resolved["room"]["game"]["round_num"], 1)
        self.assertEqual(len(resolved["room"]["game"]["history"]), 1)
        self.assertIsNone(resolved["room"]["pending_p1_move"])
        self.assertIsNone(resolved["room"]["pending_p2_move"])

    def test_room_reset_requires_both_players(self):
        room_id, p1_token, p2_token = self.create_joined_room()

        first = self.client.post(
            f"/api/rooms/{room_id}/reset",
            json={"player_token": p1_token},
        ).get_json()
        self.assertTrue(first["ok"], first)
        self.assertFalse(first["did_reset"])
        self.assertEqual(first["room"]["reset_requested_by"], "p1")

        second = self.client.post(
            f"/api/rooms/{room_id}/reset",
            json={"player_token": p2_token},
        ).get_json()
        self.assertTrue(second["ok"], second)
        self.assertTrue(second["did_reset"])
        self.assertIsNone(second["room"]["reset_requested_by"])
        self.assertEqual(second["room"]["game"]["round_num"], 0)

    def test_leave_room_deletes_room(self):
        room_id, p1_token, _ = self.create_joined_room()

        left = self.client.post(
            f"/api/rooms/{room_id}/leave",
            json={"player_token": p1_token},
        ).get_json()
        self.assertTrue(left["ok"], left)
        self.room_ids.remove(room_id)

        missing = self.client.get(f"/api/rooms/{room_id}").get_json()
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error_code"], "ROOM_NOT_FOUND")

    def test_room_can_restore_from_storage_after_memory_clear(self):
        room, _, _ = create_room("Persisted")
        self.room_ids.append(room.room_id)
        room_id = room.room_id

        ROOMS.pop(room_id, None)
        ROOM_RUNTIME_LOCKS.pop(room_id, None)

        restored = get_room(room_id)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.room_id, room_id)
        self.assertEqual(restored.p1_name, "Persisted")

    def test_socket_join_and_heartbeat_mark_player_seen(self):
        room, _, token = create_room("SocketUser")
        self.room_ids.append(room.room_id)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        room.p1_last_seen_at = old_time
        room.updated_at = old_time
        room.persist()

        client = socketio.test_client(app)
        try:
            client.emit(
                "join_room",
                {"room_id": room.room_id, "player_token": token},
            )
            updated = get_room(room.room_id)
            self.assertGreater(updated.p1_last_seen_at, old_time)

            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            updated.p1_last_seen_at = old_time
            updated.updated_at = old_time
            updated.persist()
            client.emit(
                "room_heartbeat",
                {"room_id": room.room_id, "player_token": token},
            )
            heartbeat_updated = get_room(room.room_id)
            self.assertGreater(heartbeat_updated.p1_last_seen_at, old_time)
        finally:
            client.disconnect()

    def test_room_reconnect_after_refresh(self):
        """模拟玩家刷新页面后通过 GET 房间状态恢复身份。"""
        room_id, p1_token, p2_token = self.create_joined_room()

        # P1 先提交动作
        self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": p1_token, "move_name": "QI"},
        )

        # 模拟 P1 刷新页面：通过 GET 携带 player_token 重新获取房间
        reconnected = self.client.get(
            f"/api/rooms/{room_id}?player_token={p1_token}",
        ).get_json()
        self.assertTrue(reconnected["ok"], reconnected)
        self.assertEqual(reconnected["room"]["requester_seat"], "p1")
        self.assertEqual(reconnected["room"]["pending_p1_move"], "QI")

    def test_room_submit_with_invalid_token_rejected(self):
        """测试无效 token 提交动作被拒绝。"""
        room_id, _, _ = self.create_joined_room()

        bad_submit = self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": "fake-token-123", "move_name": "QI"},
        ).get_json()
        self.assertFalse(bad_submit["ok"])
        self.assertEqual(bad_submit.get("error"), "身份无效，不能提交动作。")

    def test_room_submit_when_not_full(self):
        """测试房间未满时提交动作被拒绝。"""
        created = self.client.post(
            "/api/rooms",
            json={"player_name": "Solo"},
        ).get_json()
        self.assertTrue(created["ok"], created)
        room_id = created["room"]["room_id"]
        p1_token = created["player_token"]
        self.room_ids.append(room_id)

        submit = self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": p1_token, "move_name": "QI"},
        ).get_json()
        self.assertFalse(submit["ok"])
        self.assertIn("人数未满", submit.get("error", ""))

    def test_room_get_returns_online_status_for_both_players(self):
        """测试房间状态返回双方在线情况。"""
        room_id, p1_token, p2_token = self.create_joined_room()

        # 先通过 GET 触发 mark_seen
        self.client.get(
            f"/api/rooms/{room_id}?player_token={p1_token}",
        )

        state = self.client.get(f"/api/rooms/{room_id}").get_json()
        self.assertTrue(state["ok"], state)
        online = state["room"].get("online_status", {})
        self.assertIn("p1_online", online)
        self.assertIn("p2_online", online)

    def test_room_touch_prevents_active_room_from_expiring(self):
        room_id, p1_token, p2_token = self.create_joined_room()
        room = get_room(room_id)
        old_time = datetime.now(timezone.utc) - timedelta(hours=13)
        room.updated_at = old_time
        room.p1_last_seen_at = old_time
        room.p2_last_seen_at = old_time
        room.persist()

        self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": p1_token, "move_name": "QI"},
        )
        self.client.post(
            f"/api/rooms/{room_id}/step",
            json={"player_token": p2_token, "move_name": "QI"},
        )

        touched = get_room(room_id)
        self.assertGreater(touched.updated_at, old_time)
        self.assertFalse(touched.is_expired())

if __name__ == "__main__":
    unittest.main()
