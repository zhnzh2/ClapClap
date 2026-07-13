from flask import Blueprint, g, jsonify, request

from app.v1.game import GameEngine
from app.v1.state_api import get_game_state_payload, parse_move_name
from app.battle_recorder import create_battle, record_round, end_battle
from server.auth_middleware import require_auth
import server.runtime as runtime

local_bp = Blueprint("local", __name__)


@local_bp.get("/v1/api/local/state")
@require_auth
def get_state():
    session_key = runtime.get_local_session_key(g.current_user)
    with runtime.CURRENT_STATE_LOCK:
        session = runtime.get_local_session(session_key)
        payload = get_game_state_payload(session.state, include_history=True)
    return jsonify(payload)


@local_bp.post("/v1/api/local/reset")
@require_auth
def reset_game():
    session_key = runtime.get_local_session_key(g.current_user)
    with runtime.CURRENT_STATE_LOCK:
        session = runtime.reset_local_session(session_key)
        payload = get_game_state_payload(session.state, include_history=True)
    return jsonify(
        {
            "ok": True,
            "message": "游戏已重置。",
            "state": payload,
        }
    )


@local_bp.post("/v1/api/local/step")
@require_auth
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

    session_key = runtime.get_local_session_key(g.current_user)
    with runtime.CURRENT_STATE_LOCK:
        session = runtime.get_local_session(session_key)
        GameEngine.resolve_round(session.state, p1_move, p2_move)

        # ── 对局记录 ──────────────────────────────
        # 本地模式使用特殊参与者标识
        if session.battle_id is None:
            session.battle_id = create_battle(
                {
                    "p1": {"username": "本地玩家1", "uid": -1},
                    "p2": {"username": "本地玩家2", "uid": -1},
                }
            )

        # 记录本回合
        if session.state.history:
            latest_log = session.state.history[-1]
            record_round(session.battle_id, latest_log.to_dict())

        # 游戏结束则标记对局结束
        if session.state.winner is not None:
            end_battle(session.battle_id, session.state.winner)

        session.touch()
        payload = get_game_state_payload(session.state, include_history=True)

    return jsonify(
        {
            "ok": True,
            "message": "本回合已结算。",
            "state": payload,
        }
    )
