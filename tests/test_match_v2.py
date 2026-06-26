from __future__ import annotations

import pytest

from app.storage import delete_kv, delete_room
from app.v2 import matchmaking as matchmaking_v2
from app.v2.matchmaking import (
    MATCH_LOCK_V2,
    PLAYER_MATCH_STATE_V2,
    enqueue_v2,
    get_player_match_state_v2,
    get_queue_status_v2,
)
from app.v2.room_manager import (
    ROOMS_V2,
    ROOMS_V2_LOCK,
    create_room_v2,
    get_room_v2,
    join_room_v2,
)
from app.v2.state_api import get_room_v2_payload


class TestMatchmakingV2:
    def setup_method(self):
        with MATCH_LOCK_V2:
            matchmaking_v2.MATCH_QUEUE_V2.clear()
            PLAYER_MATCH_STATE_V2.clear()
        with ROOMS_V2_LOCK:
            ROOMS_V2.clear()
        delete_kv("v2_match_state")
        self.created_room_ids: list[str] = []

    def teardown_method(self):
        for room_id in self.created_room_ids:
            delete_room(room_id)
        with MATCH_LOCK_V2:
            matchmaking_v2.MATCH_QUEUE_V2.clear()
            PLAYER_MATCH_STATE_V2.clear()
        with ROOMS_V2_LOCK:
            ROOMS_V2.clear()
        delete_kv("v2_match_state")

    def test_match_creates_private_v2_room_and_player_identities(self):
        first = enqueue_v2("Alice", "match-v2-a", preferred_players=3)
        second = enqueue_v2("Bob", "match-v2-b", preferred_players=3)
        matched = enqueue_v2("Cora", "match-v2-c", preferred_players=3)

        assert first["matched"] is False
        assert second["matched"] is False
        assert matched["matched"] is True
        assert matched["room_player_token"]
        assert matched["seat_index"] == 3

        room_id = matched["room_id"]
        self.created_room_ids.append(room_id)
        room = get_room_v2(room_id)

        assert room is not None
        assert room.rule_version == "2.0"
        assert room.max_players == 3
        assert room.min_players == 3
        assert room.public is False
        assert room.allow_spectate is True
        assert get_queue_status_v2()["queue_size"] == 0

        alice = get_player_match_state_v2("match-v2-a")
        bob = get_player_match_state_v2("match-v2-b")
        cora = get_player_match_state_v2("match-v2-c")

        assert alice["status"] == "matched"
        assert bob["status"] == "matched"
        assert cora["status"] == "matched"
        assert {alice["seat_index"], bob["seat_index"], cora["seat_index"]} == {1, 2, 3}
        assert all(state["room_player_token"] for state in (alice, bob, cora))

    def test_room_payload_includes_sanitized_spectator_list(self):
        room, _, _ = create_room_v2("Alice", allow_spectate=True)
        self.created_room_ids.append(room.room_id)
        _, _, spectator_token = join_room_v2(room.room_id, "Viewer", as_spectator=True)

        payload = get_room_v2_payload(room, requester_token=spectator_token)

        assert payload["my_role"] == "spectator"
        assert payload["spectator_count"] == 1
        assert payload["spectators"] == [
            {
                "username": "Viewer",
                "joined_at": room.spectators[0].joined_at.isoformat(),
            }
        ]
        assert "spectator_token" not in payload["spectators"][0]
        assert spectator_token not in str(payload)

    def test_password_room_requires_password_for_players_and_spectators(self):
        room, _, _ = create_room_v2("Alice", password="secret", allow_spectate=True)
        self.created_room_ids.append(room.room_id)

        with pytest.raises(ValueError, match="PASSWORD_REQUIRED"):
            join_room_v2(room.room_id, "Bob")

        with pytest.raises(ValueError, match="密码不正确"):
            join_room_v2(room.room_id, "Bob", password="wrong")

        _, seat_index, player_token = join_room_v2(room.room_id, "Bob", password="secret")
        assert seat_index == 2
        assert room.get_seat_by_token(player_token) is not None

        _, spectator_seat, spectator_token = join_room_v2(
            room.room_id,
            "Viewer",
            as_spectator=True,
            password="secret",
        )
        assert spectator_seat == -1
        assert room.get_spectator_by_token(spectator_token) is not None
