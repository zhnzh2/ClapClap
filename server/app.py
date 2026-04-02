from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from models import GameState
from game import GameEngine

from flask import redirect, url_for
from flask_socketio import SocketIO, join_room, emit
from room_manager import create_room, get_room, join_room
from state_api import get_game_state_payload, get_room_payload, parse_move_name
from matchmaking import enqueue_or_match, get_match_status, pop_player_match_result

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

CURRENT_STATE = GameState()

@app.get("/")
def home():
    return render_template("home.html")


@app.get("/local")
def local_mode():
    return render_template("local.html")


@app.get("/rooms")
def rooms_mode():
    return render_template("rooms.html", error_message=None)


@app.get("/match")
def match_mode():
    return render_template("match.html")


@app.get("/ai")
def ai_mode():
    return render_template("ai.html")

@app.get("/room/<room_id>")
def room_detail(room_id: str):
    room = get_room(room_id)
    if room is None:
        return render_template(
            "rooms.html",
            error_message="房间不存在。"
        )
    return render_template("room_detail.html", room_id=room_id)

@app.post("/api/rooms")
def api_create_room():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_name = data.get("player_name")
    if not isinstance(player_name, str) or not player_name.strip():
        return jsonify({"ok": False, "error": "player_name 不能为空。"}), 400

    room = create_room(player_name.strip())

    return jsonify({
        "ok": True,
        "message": "房间创建成功。",
        "room": get_room_payload(room),
    })

@app.post("/api/rooms/<room_id>/join")
def api_join_room(room_id: str):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_name = data.get("player_name")
    if not isinstance(player_name, str) or not player_name.strip():
        return jsonify({"ok": False, "error": "player_name 不能为空。"}), 400

    try:
        room, seat = join_room(room_id, player_name.strip())
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    emit_room_state(room_id)

    return jsonify({
        "ok": True,
        "message": "加入房间成功。",
        "seat": seat,
        "room": get_room_payload(room),
    })

@app.get("/api/rooms/<room_id>")
def api_get_room(room_id: str):
    room = get_room(room_id)
    if room is None:
        return jsonify({"ok": False, "error": "房间不存在。"}), 404

    return jsonify({
        "ok": True,
        "room": get_room_payload(room),
    })

@app.post("/api/rooms/<room_id>/step")
def api_room_step(room_id: str):
    room = get_room(room_id)
    if room is None:
        return jsonify({"ok": False, "error": "房间不存在。"}), 404

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    seat = data.get("seat")
    move_name = data.get("move_name")

    if seat not in ("p1", "p2"):
        return jsonify({"ok": False, "error": "seat 必须是 p1 或 p2。"}), 400

    if not isinstance(move_name, str):
        return jsonify({"ok": False, "error": "move_name 必须是字符串。"}), 400

    try:
        move = parse_move_name(move_name)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    player = room.state.p1 if seat == "p1" else room.state.p2
    if not GameEngine.can_afford(player, move):
        return jsonify({"ok": False, "error": "当前动作不合法或资源不足。"}), 400

    room.submit_move(seat, move_name)

    both_ready = room.pending_p1_move is not None and room.pending_p2_move is not None

    if both_ready:
        p1_move = parse_move_name(room.pending_p1_move)
        p2_move = parse_move_name(room.pending_p2_move)

        GameEngine.resolve_round(room.state, p1_move, p2_move)
        room.clear_pending_moves()

        if room.state.winner is not None:
            room.status = "finished"
        else:
            room.status = "playing"

        emit_room_state(room_id)

        return jsonify({
            "ok": True,
            "message": "双方都已提交，本回合已结算。",
            "resolved": True,
            "room": get_room_payload(room),
        })

    emit_room_state(room_id)

    return jsonify({
        "ok": True,
        "message": f"{seat} 已提交动作，等待另一方。",
        "resolved": False,
        "room": get_room_payload(room),
    })

@app.post("/api/rooms/<room_id>/reset")
def api_room_reset(room_id: str):
    room = get_room(room_id)
    if room is None:
        return jsonify({"ok": False, "error": "房间不存在。"}), 404

    room.reset_game()
    emit_room_state(room_id)

    return jsonify({
        "ok": True,
        "message": "房间对局已重置。",
        "room": get_room_payload(room),
    })

@app.post("/api/match/join")
def api_match_join():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_name = data.get("player_name")
    if not isinstance(player_name, str) or not player_name.strip():
        return jsonify({"ok": False, "error": "player_name 不能为空。"}), 400

    result = enqueue_or_match(player_name.strip())

    if result["matched"]:
        return jsonify({
            "ok": True,
            "matched": True,
            "message": "匹配成功，已进入房间。",
            "room_id": result["room_id"],
            "p1_name": result["p1_name"],
            "p2_name": result["p2_name"],
        })

    return jsonify({
        "ok": True,
        "matched": False,
        "message": "已进入匹配队列，等待另一位玩家。",
        "waiting_player": result["waiting_player"],
    })

@app.get("/api/match/status")
def api_match_status():
    status = get_match_status()
    return jsonify({
        "ok": True,
        "status": status,
    })

@app.get("/api/match/result")
def api_match_result():
    player_name = request.args.get("player_name", type=str)
    if player_name is None or not player_name.strip():
        return jsonify({"ok": False, "error": "player_name 不能为空。"}), 400

    result = pop_player_match_result(player_name.strip())

    return jsonify({
        "ok": True,
        "matched": result["matched"],
        "room_id": result["room_id"],
        "seat": result["seat"],
    })

@app.get("/favicon.ico")
def favicon():
    return "", 204

@app.get("/state")
def get_state():
    return jsonify(get_game_state_payload(CURRENT_STATE, include_history=True))


@app.post("/reset")
def reset_game():
    global CURRENT_STATE
    CURRENT_STATE = GameState()
    return jsonify(
        {
            "ok": True,
            "message": "游戏已重置。",
            "state": get_game_state_payload(CURRENT_STATE, include_history=True),
        }
    )


@app.post("/step")
def step_game():
    global CURRENT_STATE

    data = request.get_json(silent=True)
    if data is None:
        return jsonify(
            {
                "ok": False,
                "error": "请求体必须是 JSON。"
            }
        ), 400

    p1_move_name = data.get("p1_move")
    p2_move_name = data.get("p2_move")

    if not isinstance(p1_move_name, str) or not isinstance(p2_move_name, str):
        return jsonify(
            {
                "ok": False,
                "error": "必须提供字符串类型的 p1_move 和 p2_move。"
            }
        ), 400

    try:
        p1_move = parse_move_name(p1_move_name)
        p2_move = parse_move_name(p2_move_name)
    except ValueError as exc:
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
            }
        ), 400

    GameEngine.resolve_round(CURRENT_STATE, p1_move, p2_move)

    return jsonify(
        {
            "ok": True,
            "message": "本回合已结算。",
            "state": get_game_state_payload(CURRENT_STATE, include_history=True),
        }
    )


@app.get("/health")
def health_check():
    return jsonify(
        {
            "ok": True,
            "message": "ClapClap server is running."
        }
    )

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

    join_room(room_id)
    emit_room_state(room_id)

import os

if __name__ == "__main__":
    socketio.run(app, debug=True)