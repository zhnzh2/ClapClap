from flask_socketio import emit, join_room as socket_join_room

from app.room_manager import get_room, get_room_runtime_lock
from app.state_api import get_room_payload
from app.matchmaking import get_match_status
from app.battle_recorder import record_chat
from server.extensions import socketio


def emit_room_state(room_id: str) -> None:
    room = get_room(room_id)
    if room is None:
        return

    socketio.emit(
        "room_state",
        {
            "ok": True,
            "room": get_room_payload(room),
        },
        to=room_id,
    )

def emit_opponent_left(room_id: str, left_seat: str) -> None:
    socketio.emit(
        "opponent_left",
        {
            "ok": True,
            "room_id": room_id,
            "left_seat": left_seat,
        },
        to=room_id,
    )

def emit_match_status() -> None:
    socketio.emit(
        "match_status",
        {
            "ok": True,
            "status": get_match_status(),
        },
        to="match_lobby",
    )

@socketio.on("join_room")
def handle_join_room(data):
    room_id = data.get("room_id")
    if not isinstance(room_id, str):
        emit("room_error", {"ok": False, "error": "room_id 无效。"})
        return

    room = get_room(room_id)
    if room is None:
        emit("room_error", {"ok": False, "error": "房间不存在。"})
        return

    player_token = data.get("player_token")
    if isinstance(player_token, str) and player_token.strip():
        seat = room.get_seat_by_token(player_token.strip())
        if seat in ("p1", "p2"):
            with get_room_runtime_lock(room_id):
                room.mark_seen(seat)

    socket_join_room(room_id)
    emit_room_state(room_id)

@socketio.on("room_heartbeat")
def handle_room_heartbeat(data):
    room_id = data.get("room_id")
    player_token = data.get("player_token")

    if not isinstance(room_id, str) or not isinstance(player_token, str):
        return

    room = get_room(room_id)
    if room is None:
        return

    seat = room.get_seat_by_token(player_token.strip())
    if seat not in ("p1", "p2"):
        return

    with get_room_runtime_lock(room_id):
        room.mark_seen(seat)

@socketio.on("join_match_lobby")
def handle_join_match_lobby():
    socket_join_room("match_lobby")
    emit(
        "match_status",
        {
            "ok": True,
            "status": get_match_status(),
        },
    )


@socketio.on("chat_message")
def handle_chat_message(data):
    """聊天消息: {room_id, message}。发送者从 player_token 推断。"""
    room_id = data.get("room_id")
    message = (data.get("message") or "").strip()
    player_token = (data.get("player_token") or "").strip()

    if not isinstance(room_id, str) or not message:
        emit("chat_error", {"ok": False, "error": "消息不能为空。"})
        return

    if len(message) > 50:
        emit("chat_error", {"ok": False, "error": "消息不能超过 50 个字符。"})
        return

    room = get_room(room_id)
    if room is None:
        emit("chat_error", {"ok": False, "error": "房间不存在。"})
        return

    # 确定发送者
    sender = None
    if player_token:
        seat = room.get_seat_by_token(player_token)
        if seat == "p1":
            sender = room.p1_name
        elif seat == "p2":
            sender = room.p2_name

    if sender is None:
        sender = player_token or "未知"

    # 保存到房间
    with get_room_runtime_lock(room_id):
        msg = room.add_chat_message(sender, message)

    # 同步到对局记录
    if room.battle_id:
        try:
            record_chat(room.battle_id, msg["timestamp"], msg["sender"], msg["message"])
        except Exception:
            pass

    # 广播给房间内所有人
    emit("chat_broadcast", {"ok": True, "message": msg}, to=room_id)
