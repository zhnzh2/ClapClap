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
        # 检查是参战者还是观战者
        seat = room.get_seat_by_token(player_token.strip())
        if seat is not None:
            mark_reconnected_v2(room_id, player_token.strip())
        else:
            spec = room.get_spectator_by_token(player_token.strip())
            if spec is None:
                emit("room_v2_error", {"ok": False, "error": "身份无效。"})
                return

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


def persist_room_v2(room) -> None:
    """持久化 v2 房间（从 socket_events 调用的便捷函数）。"""
    from app.v2.room_manager import persist_room_v2 as _persist
    _persist(room)
