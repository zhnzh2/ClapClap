from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Optional

from room_manager import create_room, join_room
from storage import load_kv, save_kv

@dataclass
class WaitingPlayer:
    player_name: str
    player_token: str
    joined_at: datetime

MATCH_WAITING: Optional[WaitingPlayer] = None
MATCH_RESULTS: dict[str, dict] = {}
MATCH_LOCK = RLock()

def persist_match_state() -> None:
    waiting_data = None
    if MATCH_WAITING is not None:
        waiting_data = {
            "player_name": MATCH_WAITING.player_name,
            "player_token": MATCH_WAITING.player_token,
            "joined_at": MATCH_WAITING.joined_at.isoformat(),
        }

    save_kv(
        "match_state",
        {
            "waiting": waiting_data,
            "results": MATCH_RESULTS,
        },
    )


def load_match_state() -> None:
    global MATCH_WAITING, MATCH_RESULTS

    data = load_kv("match_state")
    if data is None:
        return

    waiting = data.get("waiting")
    results = data.get("results", {})

    MATCH_RESULTS.clear()
    MATCH_RESULTS.update(results)

    if waiting is None:
        MATCH_WAITING = None
    else:
        MATCH_WAITING = WaitingPlayer(
            player_name=waiting["player_name"],
            player_token=waiting["player_token"],
            joined_at=datetime.fromisoformat(waiting["joined_at"]),
        )

def enqueue_or_match(player_name: str, player_token: str) -> dict:
    global MATCH_WAITING

    with MATCH_LOCK:
        if MATCH_WAITING is None:
            MATCH_WAITING = WaitingPlayer(
                player_name=player_name,
                player_token=player_token,
                joined_at=datetime.utcnow(),
            )
            persist_match_state()
            return {
                "matched": False,
                "waiting_player": player_name,
            }

        first_player = MATCH_WAITING
        MATCH_WAITING = None

        room, _, p1_token = create_room(first_player.player_name)
        _, seat, p2_token = room, "p2", None
        _, _, p2_token = join_room(room.room_id, player_name)

        MATCH_RESULTS[first_player.player_token] = {
            "room_id": room.room_id,
            "seat": "p1",
            "player_token": p1_token,
        }
        MATCH_RESULTS[player_token] = {
            "room_id": room.room_id,
            "seat": "p2",
            "player_token": p2_token,
        }

        persist_match_state()

        return {
            "matched": True,
            "room_id": room.room_id,
            "p1_name": room.p1_name,
            "p2_name": room.p2_name,
            "seat": "p2",
            "player_token": p2_token,
        }

def get_match_status() -> dict:
    with MATCH_LOCK:
        if MATCH_WAITING is None:
            return {
                "has_waiting_player": False,
                "waiting_player": None,
            }

        return {
            "has_waiting_player": True,
            "waiting_player": MATCH_WAITING.player_name,
        }

def get_player_match_result(player_token: str) -> dict:
    with MATCH_LOCK:
        result = MATCH_RESULTS.get(player_token)
        if result is None:
            return {
                "matched": False,
                "room_id": None,
                "seat": None,
                "player_token": None,
            }

        return {
            "matched": True,
            "room_id": result["room_id"],
            "seat": result["seat"],
            "player_token": result["player_token"],
        }

def pop_player_match_result(player_token: str) -> dict:
    with MATCH_LOCK:
        result = MATCH_RESULTS.pop(player_token, None)
        persist_match_state()

        if result is None:
            return {
                "matched": False,
                "room_id": None,
                "seat": None,
                "player_token": None,
            }

        return {
            "matched": True,
            "room_id": result["room_id"],
            "seat": result["seat"],
            "player_token": result["player_token"],
        }