"""
ClapClap 2.0 Socket.IO 事件处理。

与 1.0 (server/socket_events.py) 完全独立。
处理 v2 多人房间的实时通信。
"""

from flask import request as flask_request
from flask_socketio import emit, join_room as socket_join_room

from app.v2.room_manager import get_room_v2, mark_seen_v2, mark_disconnected_v2, mark_reconnected_v2
from app.v2.state_api import get_room_v2_payload
from server.extensions import socketio


def _player_socket_room(room_id: str, player_token: str) -> str:
    return f"{room_id}:player:{player_token}"


# ═══════════════════════════════════════════════════════
# 广播辅助函数
# ═══════════════════════════════════════════════════════

def emit_room_v2_state(room_id: str) -> None:
    """广播 v2 房间状态给房间内所有人。"""
    room = get_room_v2(room_id)
    if room is None:
        return

    socketio.emit(
        "room_v2_state",
        {
            "ok": True,
            "room": get_room_v2_payload(room),
        },
        to=room_id,
    )


def emit_player_left_v2(room_id: str, player_token: str, leave_type: str) -> None:
    """广播玩家离开。"""
    socketio.emit(
        "player_left_v2",
        {
            "ok": True,
            "room_id": room_id,
            "player_token": player_token,
            "leave_type": leave_type,
        },
        to=room_id,
    )


def emit_host_changed_v2(room_id: str, new_host_token: str) -> None:
    """广播房主转移。"""
    room = get_room_v2(room_id)
    if room is None:
        return

    new_host_seat = room.get_seat_by_token(new_host_token)
    socketio.emit(
        "host_changed_v2",
        {
            "ok": True,
            "room_id": room_id,
            "new_host_seat_index": new_host_seat.seat_index if new_host_seat else None,
            "new_host_username": new_host_seat.username if new_host_seat else None,
        },
        to=room_id,
    )


def emit_game_started_v2(room_id: str) -> None:
    """广播对局开始。"""
    room = get_room_v2(room_id)
    if room is None:
        return

    socketio.emit(
        "game_started_v2",
        {
            "ok": True,
            "room_id": room_id,
        },
        to=room_id,
    )


# ═══════════════════════════════════════════════════════
# Socket.IO 事件处理
# ═══════════════════════════════════════════════════════

@socketio.on("join_room_v2")
def handle_join_room_v2(data):
    """加入 v2 房间的 Socket.IO 频道。"""
    room_id = data.get("room_id")
    if not isinstance(room_id, str):
        emit("room_v2_error", {"ok": False, "error": "room_id 无效。"})
        return

    room = get_room_v2(room_id)
    if room is None:
        emit("room_v2_error", {"ok": False, "error": "房间不存在。"})
        return

    player_token = data.get("player_token")
    if isinstance(player_token, str) and player_token.strip():
        player_token = player_token.strip()
        # 检查是参战者还是观战者
        seat = room.get_seat_by_token(player_token)
        if seat is not None:
            mark_reconnected_v2(room_id, player_token)
            socket_join_room(_player_socket_room(room_id, player_token))
        else:
            spec = room.get_spectator_by_token(player_token)
            if spec is None:
                emit("room_v2_error", {"ok": False, "error": "身份无效。"})
                return
            socket_join_room(_player_socket_room(room_id, player_token))

    socket_join_room(room_id)
    emit_room_v2_state(room_id)


@socketio.on("room_v2_heartbeat")
def handle_room_v2_heartbeat(data):
    """v2 房间心跳。"""
    room_id = data.get("room_id")
    player_token = data.get("player_token")

    if not isinstance(room_id, str) or not isinstance(player_token, str):
        return

    room = get_room_v2(room_id)
    if room is None:
        return

    seat = room.get_seat_by_token(player_token.strip())
    if seat is None:
        return

    mark_seen_v2(room_id, player_token.strip())


@socketio.on("disconnect")
def handle_disconnect_v2():
    """Socket.IO 断连时标记玩家离线。"""
    # 无法直接从 disconnect 事件获取 room_id 和 player_token
    # 需要由前端在断连前发送 leave_room_v2 事件
    pass


@socketio.on("chat_message_v2")
def handle_chat_message_v2(data):
    """v2 房间聊天消息。"""
    room_id = data.get("room_id")
    message = (data.get("message") or "").strip()
    player_token = (data.get("player_token") or "").strip()

    if not isinstance(room_id, str) or not message:
        emit("chat_v2_error", {"ok": False, "error": "消息不能为空。"})
        return

    if len(message) > 50:
        emit("chat_v2_error", {"ok": False, "error": "消息不能超过 50 个字符。"})
        return

    room = get_room_v2(room_id)
    if room is None:
        emit("chat_v2_error", {"ok": False, "error": "房间不存在。"})
        return

    # 确定发送者
    sender = None
    if player_token:
        seat = room.get_seat_by_token(player_token)
        if seat is not None:
            sender = seat.username
        else:
            spec = room.get_spectator_by_token(player_token)
            if spec is not None:
                sender = f"{spec.username}(观战)"

    if sender is None:
        sender = player_token or "未知"

    # 保存到房间
    msg = room.add_chat_message(sender, message)
    persist_room_v2(room)

    # 广播给房间内所有人
    emit("chat_v2_broadcast", {"ok": True, "message": msg}, to=room_id)


def emit_round_summary_v2(room_id: str) -> None:
    """广播回合总结给房间内所有人。"""
    room = get_room_v2(room_id)
    if room is None or room.game_state is None:
        return

    from app.v2.state_api import get_round_summary_payload

    summary = get_round_summary_payload(room.game_state)
    if summary is None:
        return

    socketio.emit(
        "round_summary_v2",
        {
            "ok": True,
            "room_id": room_id,
            "summary": summary,
        },
        to=room_id,
    )


def emit_settlement_progress_v2(room_id: str, step_result) -> None:
    """广播结算进度给房间内所有人。

    Args:
        room_id: 房间 ID
        step_result: SettlementStepResult 实例
    """
    result_dict = step_result.to_dict() if hasattr(step_result, 'to_dict') else step_result

    # 广播给所有玩家（更新游戏进度）
    socketio.emit(
        "settlement_progress_v2",
        {
            "ok": True,
            "room_id": room_id,
            "action": result_dict.get("action", ""),
            "phase": result_dict.get("phase", ""),
            "sub_phase": result_dict.get("sub_phase", ""),
            "current_speed_layer": result_dict.get("current_speed_layer", 0),
            "progress_data": result_dict.get("progress_data", {}),
        },
        to=room_id,
    )

    # 如果有决策请求，只把完整选项发给对应玩家。
    decision_requests = result_dict.get("decision_requests", [])
    if decision_requests:
        room = get_room_v2(room_id)
        if room is None:
            return

        public_summary = []
        for req in decision_requests:
            player_id = req.get("player_id", "")
            seat = room.get_seat_by_player_id(player_id)
            if seat is None:
                continue

            payload = {
                "ok": True,
                "room_id": room_id,
                "decision_request": req,
            }
            socketio.emit(
                "decision_request_v2",
                payload,
                to=_player_socket_room(room_id, seat.player_token),
            )
            public_summary.append({
                "decision_id": req.get("decision_id", ""),
                "decision_type": req.get("decision_type", ""),
                "speed_layer": req.get("speed_layer", 0),
                "player_id": player_id,
                "split_count": req.get("split_count", 1),
                "negotiation_round": req.get("negotiation_round", 0),
            })

        socketio.emit(
            "decision_requests_summary_v2",
            {
                "ok": True,
                "room_id": room_id,
                "decision_requests": public_summary,
            },
            to=room_id,
        )


@socketio.on("submit_decision_v2")
def handle_submit_decision_v2(data):
    """玩家通过 Socket.IO 提交结算决策。"""
    room_id = data.get("room_id")
    player_token = data.get("player_token")
    decisions = data.get("decisions", {})

    if not isinstance(room_id, str) or not isinstance(player_token, str):
        emit("decision_v2_error", {"ok": False, "error": "参数无效。"})
        return

    from server.services.room_v2_service import submit_decision_v2_service

    response_data, status = submit_decision_v2_service(room_id, player_token, decisions)

    if status >= 400:
        emit("decision_v2_error", {
            "ok": False,
            "error": response_data.get("error", "决策提交失败。"),
        })


@socketio.on("leave_room_v2")
def handle_leave_room_v2(data):
    """玩家主动离开 v2 房间的 Socket.IO 频道。"""
    room_id = data.get("room_id")
    if isinstance(room_id, str):
        # 只是离开 Socket.IO 房间，不退出游戏房间
        from flask_socketio import leave_room
        leave_room(room_id)


def persist_room_v2(room) -> None:
    """持久化 v2 房间（从 socket_events 调用的便捷函数）。"""
    from app.v2.room_manager import persist_room_v2 as _persist
    _persist(room)
