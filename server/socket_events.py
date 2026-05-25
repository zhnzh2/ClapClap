from flask_socketio import emit, join_room as socket_join_room

from app.room_manager import get_room, get_room_runtime_lock
from app.state_api import get_room_payload
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
