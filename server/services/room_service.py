from __future__ import annotations

from app.game import GameEngine
from app.v2.game import GameEngineV2
from app.room_manager import (
    create_room,
    get_room,
    join_room as room_join_room,
    get_room_runtime_lock,
    delete_room_by_id,
)
from app.state_api import get_room_payload, parse_move_name
from app.matchmaking import clear_match_state_by_room
from app.battle_recorder import create_battle, record_round, end_battle
from server.runtime import run_periodic_cleanup
from server.socket_events import emit_room_state


def _lookup_uid(username: str) -> int:
    """根据用户名查找 UID。用于对局记录。"""
    from app.users import lookup_uid
    return lookup_uid(username)


def create_room_service(player_name: str, rule_version: str = "1.0") -> dict:
    room, seat, player_token = create_room(player_name.strip(), rule_version=rule_version)

    return {
        "ok": True,
        "message": "房间创建成功。",
        "seat": seat,
        "player_token": player_token,
        "room": get_room_payload(room),
    }


def join_room_service(room_id: str, player_name: str) -> dict:
    room, seat, player_token = room_join_room(room_id, player_name.strip())

    emit_room_state(room_id)

    return {
        "ok": True,
        "message": "加入房间成功。",
        "seat": seat,
        "player_token": player_token,
        "room": get_room_payload(room),
    }


def get_room_service(room_id: str, player_token: str | None) -> tuple[dict, int]:
    run_periodic_cleanup()

    room = get_room(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    requester_seat = None
    if player_token:
        requester_seat = room.get_seat_by_token(player_token.strip())
        if requester_seat in ("p1", "p2"):
            room.mark_seen(requester_seat)

    payload = get_room_payload(room)
    payload["requester_seat"] = requester_seat

    return {
        "ok": True,
        "room": payload,
    }, 200


def submit_room_move_service(
    room_id: str,
    player_token: str,
    move_name: str,
) -> tuple[dict, int]:
    room = get_room(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    room_lock = get_room_runtime_lock(room_id)

    with room_lock:
        seat = room.get_seat_by_token(player_token.strip())
        if seat not in ("p1", "p2"):
            print(
                "[submit_room_move_service] 身份校验失败:",
                "room_id=", room_id,
                "player_token=", player_token,
                "p1_token=", room.p1_token,
                "p2_token=", room.p2_token,
            )
            return {
                "ok": False,
                "error": "身份无效，不能提交动作。",
            }, 403

        room.mark_seen(seat)

        if room.status == "finished":
            return {
                "ok": False,
                "error": "当前对局已结束。",
            }, 400

        if not room.is_full():
            return {
                "ok": False,
                "error": "房间人数未满，暂不能开始。",
            }, 400

        if seat == "p1" and room.pending_p1_move is not None:
            return {
                "ok": False,
                "error": "你本回合已经提交过动作。",
            }, 400

        if seat == "p2" and room.pending_p2_move is not None:
            return {
                "ok": False,
                "error": "你本回合已经提交过动作。",
            }, 400

        try:
            move = parse_move_name(move_name)
        except ValueError as exc:
            return {
                "ok": False,
                "error": str(exc),
            }, 400

        player = room.state.p1 if seat == "p1" else room.state.p2
        if not GameEngine.can_afford(player, move):
            return {
                "ok": False,
                "error": "当前动作不合法或资源不足。",
            }, 400

        room.submit_move(seat, move_name)

        both_ready = room.pending_p1_move is not None and room.pending_p2_move is not None

        if both_ready:
            resolved_p1_move_name = room.pending_p1_move
            resolved_p2_move_name = room.pending_p2_move

            p1_move = parse_move_name(resolved_p1_move_name)
            p2_move = parse_move_name(resolved_p2_move_name)

            # ── 引擎分发 ──────────────────────────────────
            rule_version = room.rule_version
            if rule_version == "1.0":
                GameEngine.resolve_round(room.state, p1_move, p2_move)
            elif rule_version == "2.0":
                return {
                    "ok": False,
                    "error": "2.0 规则引擎尚未实现。阶段 4 完成后可用。",
                }, 400
            else:
                return {
                    "ok": False,
                    "error": f"未知的规则版本: {rule_version}",
                }, 400
            round_num = room.state.round_num
            room.clear_pending_moves()

            if room.state.winner is not None:
                room.status = "finished"
            else:
                room.status = "playing"

            # ── 对局记录 ──────────────────────────────────
            # 首次结算时创建对局记录
            if room.battle_id is None:
                participants = {}
                if room.p1_name:
                    p1_uid = _lookup_uid(room.p1_name)
                    if p1_uid >= 0:
                        participants["p1"] = {"username": room.p1_name, "uid": p1_uid}
                if room.p2_name:
                    p2_uid = _lookup_uid(room.p2_name)
                    if p2_uid >= 0:
                        participants["p2"] = {"username": room.p2_name, "uid": p2_uid}
                if len(participants) == 2:
                    room.battle_id = create_battle(participants, rule_version=rule_version)

            # 记录回合（传入完整 RoundLog 数据以支持回放）
            if room.battle_id:
                latest_log = room.state.history[-1]
                record_round(room.battle_id, latest_log.to_dict())

                # 如果游戏结束
                if room.status == "finished":
                    winner = room.state.winner  # 1, 2, 0, None
                    end_battle(room.battle_id, winner)
            # ── 对局记录结束 ──────────────────────────────

            room.touch()
            emit_room_state(room_id)

            return {
                "ok": True,
                "message": "双方都已提交，本回合已结算。",
                "resolved": True,
                "resolved_preview": {
                    "p1_move": resolved_p1_move_name,
                    "p2_move": resolved_p2_move_name,
                },
                "room": get_room_payload(room),
            }, 200

        emit_room_state(room_id)

        return {
            "ok": True,
            "message": f"{seat} 已提交动作，等待另一方。",
            "resolved": False,
            "room": get_room_payload(room),
        }, 200


def reset_room_service(room_id: str, player_token: str) -> tuple[dict, int]:
    run_periodic_cleanup()

    room = get_room(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    room_lock = get_room_runtime_lock(room_id)

    with room_lock:
        seat = room.get_seat_by_token(player_token.strip())
        if seat not in ("p1", "p2"):
            return {
                "ok": False,
                "error": "身份无效，不能重置房间。",
            }, 403

        room.mark_seen(seat)

        did_reset, message = room.request_reset(seat)

        emit_room_state(room_id)

        return {
            "ok": True,
            "did_reset": did_reset,
            "message": message,
            "room": get_room_payload(room),
        }, 200
    
def cancel_room_move_service(room_id: str, player_token: str) -> tuple[dict, int]:
    room = get_room(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    room_lock = get_room_runtime_lock(room_id)

    with room_lock:
        seat = room.get_seat_by_token(player_token.strip())
        if seat not in ("p1", "p2"):
            return {
                "ok": False,
                "error": "身份无效，不能撤回动作。",
            }, 403

        room.mark_seen(seat)

        success, message = room.cancel_submitted_move(seat)
        if not success:
            return {
                "ok": False,
                "error": message,
            }, 400

        emit_room_state(room_id)

        return {
            "ok": True,
            "message": message,
            "room": get_room_payload(room),
        }, 200
    
def leave_room_service(room_id: str, player_token: str) -> tuple[dict, int]:
    room = get_room(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    room_lock = get_room_runtime_lock(room_id)

    with room_lock:
        seat = room.get_seat_by_token(player_token.strip())
        if seat not in ("p1", "p2"):
            return {
                "ok": False,
                "error": "身份无效，不能退出房间。",
            }, 403

        from server.socket_events import emit_opponent_left

        emit_opponent_left(room_id, seat)
        clear_match_state_by_room(room_id)
        delete_room_by_id(room_id)

        return {
            "ok": True,
            "message": "你已退出房间。",
        }, 200
