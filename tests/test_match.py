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


if __name__ == "__main__":
    unittest.main()
