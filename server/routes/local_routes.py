from flask import Blueprint, jsonify, request

from app.game import GameEngine
from app.state_api import get_game_state_payload, parse_move_name
import server.runtime as runtime

local_bp = Blueprint("local", __name__)


@local_bp.get("/state")
@local_bp.get("/api/local/state")
def get_state():
    with runtime.CURRENT_STATE_LOCK:
        payload = get_game_state_payload(runtime.CURRENT_STATE, include_history=True)
    return jsonify(payload)


@local_bp.post("/reset")
@local_bp.post("/api/local/reset")
def reset_game():
    with runtime.CURRENT_STATE_LOCK:
        runtime.CURRENT_STATE = runtime.CURRENT_STATE.__class__()
        payload = get_game_state_payload(runtime.CURRENT_STATE, include_history=True)
    return jsonify(
        {
            "ok": True,
            "message": "游戏已重置。",
            "state": payload,
        }
    )


@local_bp.post("/step")
@local_bp.post("/api/local/step")
def step_game():
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

    with runtime.CURRENT_STATE_LOCK:
        GameEngine.resolve_round(runtime.CURRENT_STATE, p1_move, p2_move)
        payload = get_game_state_payload(runtime.CURRENT_STATE, include_history=True)

    return jsonify(
        {
            "ok": True,
            "message": "本回合已结算。",
            "state": payload,
        }
    )


@local_bp.get("/health")
def health_check():
    return jsonify(
        {
            "ok": True,
            "message": "ClapClap server is running."
        }
    )

