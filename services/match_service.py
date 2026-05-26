from __future__ import annotations

from app.matchmaking import (
    enqueue_or_match,
    get_match_status,
    pop_player_match_result,
    get_player_match_state,
    cancel_match,
)
from server.runtime import run_periodic_cleanup


def join_match_service(player_name: str, player_token: str) -> tuple[dict, int]:
    try:
        run_periodic_cleanup()

        result = enqueue_or_match(player_name.strip(), player_token.strip())
        from server.socket_events import emit_match_status
        emit_match_status()

        if result["matched"]:
            return {
                "ok": True,
                "matched": True,
                "message": "匹配成功，已进入房间。" if not result.get("already_in_room") else "你已经在房间中，正在返回。",
                "room_id": result["room_id"],
                "p1_name": result["p1_name"],
                "p2_name": result["p2_name"],
                "seat": result["seat"],
                "room_player_token": result.get("room_player_token"),
                "already_in_room": result.get("already_in_room", False),
            }, 200

        return {
            "ok": True,
            "matched": False,
            "message": "已进入匹配队列，等待另一位玩家。",
            "waiting_player": result["waiting_player"],
        }, 200
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {
            "ok": False,
            "error": f"匹配接口内部报错：{exc}",
        }, 500


def get_match_status_service() -> tuple[dict, int]:
    run_periodic_cleanup()
    status = get_match_status()
    return {
        "ok": True,
        "status": status,
    }, 200


def get_my_match_state_service(player_token: str) -> tuple[dict, int]:
    run_periodic_cleanup()
    state = get_player_match_state(player_token.strip())

    return {
        "ok": True,
        "state": state,
    }, 200


def cancel_match_service(player_token: str) -> tuple[dict, int]:
    run_periodic_cleanup()
    result = cancel_match(player_token.strip())
    from server.socket_events import emit_match_status
    emit_match_status()
    return result, 200


def pop_match_result_service(player_token: str) -> tuple[dict, int]:
    result = pop_player_match_result(player_token.strip())

    return {
        "ok": True,
        "matched": result["matched"],
        "room_id": result["room_id"],
        "seat": result["seat"],
        "room_player_token": result["room_player_token"],
    }, 200
