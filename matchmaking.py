from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from room_manager import create_room, join_room


@dataclass
class WaitingPlayer:
    player_name: str
    joined_at: datetime


MATCH_WAITING: Optional[WaitingPlayer] = None
MATCH_RESULTS: dict[str, dict] = {}

def enqueue_or_match(player_name: str) -> dict:
    global MATCH_WAITING

    if MATCH_WAITING is None:
        MATCH_WAITING = WaitingPlayer(
            player_name=player_name,
            joined_at=datetime.utcnow(),
        )
        return {
            "matched": False,
            "waiting_player": player_name,
        }

    first_player = MATCH_WAITING
    MATCH_WAITING = None

    room = create_room(first_player.player_name)
    join_room(room.room_id, player_name)

    MATCH_RESULTS[first_player.player_name] = {
        "room_id": room.room_id,
        "seat": "p1",
    }
    MATCH_RESULTS[player_name] = {
        "room_id": room.room_id,
        "seat": "p2",
    }

    return {
        "matched": True,
        "room_id": room.room_id,
        "p1_name": room.p1_name,
        "p2_name": room.p2_name,
    }


def get_match_status() -> dict:
    if MATCH_WAITING is None:
        return {
            "has_waiting_player": False,
            "waiting_player": None,
        }

    return {
        "has_waiting_player": True,
        "waiting_player": MATCH_WAITING.player_name,
    }

def get_player_match_result(player_name: str) -> dict:
    result = MATCH_RESULTS.get(player_name)
    if result is None:
        return {
            "matched": False,
            "room_id": None,
            "seat": None,
        }

    return {
        "matched": True,
        "room_id": result["room_id"],
        "seat": result["seat"],
    }

def pop_player_match_result(player_name: str) -> dict:
    result = MATCH_RESULTS.pop(player_name, None)
    if result is None:
        return {
            "matched": False,
            "room_id": None,
            "seat": None,
        }

    return {
        "matched": True,
        "room_id": result["room_id"],
        "seat": result["seat"],
    }