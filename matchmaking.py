from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Optional
import traceback

from room_manager import create_room, join_room
from storage import load_kv, save_kv

@dataclass
class WaitingPlayer:
    player_name: str
    player_token: str
    joined_at: datetime

MATCH_WAITING: Optional[WaitingPlayer] = None
PLAYER_MATCH_STATE: dict[str, dict] = {}
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
            "player_states": PLAYER_MATCH_STATE,
        },
    )


def load_match_state() -> None:
    global MATCH_WAITING

    data = load_kv("match_state")
    if data is None:
        return

    try:
        waiting = data.get("waiting")
        player_states = data.get("player_states", {})

        PLAYER_MATCH_STATE.clear()
        PLAYER_MATCH_STATE.update(player_states)

        if waiting is None:
            MATCH_WAITING = None
        else:
            MATCH_WAITING = WaitingPlayer(
                player_name=waiting["player_name"],
                player_token=waiting["player_token"],
                joined_at=datetime.fromisoformat(waiting["joined_at"]),
            )
    except Exception as exc:
        print(f"[load_match_state] 跳过无法兼容的旧匹配状态: {exc}")
        traceback.print_exc()
        MATCH_WAITING = None
        PLAYER_MATCH_STATE.clear()

def set_player_match_state(
    player_token: str,
    *,
    status: str,
    player_name: str | None = None,
    room_id: str | None = None,
    seat: str | None = None,
    room_player_token: str | None = None,
) -> None:
    PLAYER_MATCH_STATE[player_token] = {
        "status": status,
        "player_name": player_name,
        "room_id": room_id,
        "seat": seat,
        "room_player_token": room_player_token,
    }

def enqueue_or_match(player_name: str, player_token: str) -> dict:
    global MATCH_WAITING

    with MATCH_LOCK:
        existing = PLAYER_MATCH_STATE.get(player_token)
        if existing is not None:
            if existing["status"] == "matched":
                return {
                    "matched": True,
                    "room_id": existing["room_id"],
                    "seat": existing["seat"],
                    "room_player_token": existing.get("room_player_token"),
                    "p1_name": None,
                    "p2_name": None,
                    "already_in_room": True,
                }

            if existing["status"] == "queued":
                return {
                    "matched": False,
                    "waiting_player": player_name,
                    "already_queued": True,
                }

        if MATCH_WAITING is None:
            MATCH_WAITING = WaitingPlayer(
                player_name=player_name,
                player_token=player_token,
                joined_at=datetime.utcnow(),
            )

            set_player_match_state(
                player_token,
                status="queued",
                player_name=player_name,
            )
            persist_match_state()

            return {
                "matched": False,
                "waiting_player": player_name,
                "already_queued": False,
            }

        if MATCH_WAITING.player_token == player_token:
            return {
                "matched": False,
                "waiting_player": player_name,
                "already_queued": True,
            }

        first_player = MATCH_WAITING
        MATCH_WAITING = None

        room, _, p1_room_token = create_room(first_player.player_name)
        _, _, p2_room_token = join_room(room.room_id, player_name)

        set_player_match_state(
            first_player.player_token,
            status="matched",
            player_name=first_player.player_name,
            room_id=room.room_id,
            seat="p1",
            room_player_token=p1_room_token,
        )
        set_player_match_state(
            player_token,
            status="matched",
            player_name=player_name,
            room_id=room.room_id,
            seat="p2",
            room_player_token=p2_room_token,
        )

        persist_match_state()

        return {
            "matched": True,
            "room_id": room.room_id,
            "p1_name": room.p1_name,
            "p2_name": room.p2_name,
            "seat": "p2",
            "room_player_token": p2_room_token,
            "already_in_room": False,
        }

def get_player_match_state(player_token: str) -> dict:
    with MATCH_LOCK:
        state = PLAYER_MATCH_STATE.get(player_token)
        if state is None:
            return {
                "status": "idle",
                "player_name": None,
                "room_id": None,
                "seat": None,
                "room_player_token": None,
            }

        return {
            "status": state["status"],
            "player_name": state.get("player_name"),
            "room_id": state.get("room_id"),
            "seat": state.get("seat"),
            "room_player_token": state.get("room_player_token"),
        }
    
def cancel_match(player_token: str) -> dict:
    global MATCH_WAITING

    with MATCH_LOCK:
        state = PLAYER_MATCH_STATE.get(player_token)
        if state is None:
            return {
                "ok": True,
                "cancelled": False,
                "message": "当前不在匹配队列中。",
            }

        if state["status"] == "matched":
            return {
                "ok": True,
                "cancelled": False,
                "message": "你已经匹配到房间，不能取消匹配。",
            }

        if MATCH_WAITING is not None and MATCH_WAITING.player_token == player_token:
            MATCH_WAITING = None

        PLAYER_MATCH_STATE[player_token] = {
            "status": "idle",
            "player_name": state.get("player_name"),
            "room_id": None,
            "seat": None,
        }
        persist_match_state()

        return {
            "ok": True,
            "cancelled": True,
            "message": "已退出匹配队列。",
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
        result = PLAYER_MATCH_STATE.get(player_token)
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
        state = PLAYER_MATCH_STATE.get(player_token)
        if state is None or state["status"] != "matched":
            return {
                "matched": False,
                "room_id": None,
                "seat": None,
                "room_player_token": None,
            }

        return {
            "matched": True,
            "room_id": state["room_id"],
            "seat": state["seat"],
            "room_player_token": state.get("room_player_token"),
        }