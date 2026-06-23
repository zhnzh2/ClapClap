from flask import Blueprint, jsonify, request

from app.game import GameEngine
from app.state_api import get_game_state_payload, parse_move_name
from app.battle_recorder import create_battle, record_round, end_battle
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
        runtime.CURRENT_BATTLE_ID = None
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

        # ── 对局记录 ──────────────────────────────
        # 本地模式使用特殊参与者标识
        if runtime.CURRENT_BATTLE_ID is None:
            runtime.CURRENT_BATTLE_ID = create_battle(
                {
                    "p1": {"username": "本地玩家1", "uid": -1},
                    "p2": {"username": "本地玩家2", "uid": -1},
                }
            )

        # 记录本回合
        if runtime.CURRENT_STATE.history:
            latest_log = runtime.CURRENT_STATE.history[-1]
            record_round(runtime.CURRENT_BATTLE_ID, latest_log.to_dict())

        # 游戏结束则标记对局结束
        if runtime.CURRENT_STATE.winner is not None:
            end_battle(runtime.CURRENT_BATTLE_ID, runtime.CURRENT_STATE.winner)

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

