"""
ClapClap 1.0 AI 对战 API。

端点:
  GET  /api/ai/state  — 获取当前 AI 对战状态
  POST /api/ai/reset  — 重置 AI 对战
  POST /api/ai/step   — 提交真人动作 + AI 决策 + 结算

兼容 1.0 版本化路径:
  GET  /v1/api/ai/state
  POST /v1/api/ai/reset
  POST /v1/api/ai/step
"""

from __future__ import annotations

import random
import time

from flask import Blueprint, g, jsonify, request

from app.ai.engine import select_move
from app.ai.model_runtime import (
    model_status_for_difficulty,
    model_version_for_difficulty,
    policy_type_for_difficulty,
)
from app.ai.space import ACTION_SPACE_SIZE, get_action_space_fingerprint
from app.battle_recorder import (
    create_battle,
    end_battle,
    record_round,
    set_battle_metadata,
)
from app.v1.game import GameEngine
from app.v1.state_api import get_game_state_payload, parse_move_name
from server.auth_middleware import get_current_username, require_auth
import server.runtime as runtime

ai_bp = Blueprint("ai", __name__)
AI_OBSERVATION_VERSION = "clapclap-v1-public-state-v1"


def _get_ai_session_key() -> str:
    return runtime.get_ai_session_key(g.current_user)


def _get_ai_state_payload(session: runtime.AISession) -> dict:
    payload = get_game_state_payload(session.state, include_history=True)
    payload["battle_id"] = session.battle_id
    payload["ai_difficulty"] = session.difficulty
    payload["human_seat"] = session.human_seat
    payload["ai_seat"] = session.ai_seat
    payload["ai_policy_type"] = session.policy_type
    return payload


# ---------------------------------------------------------------------------
# GET /api/ai/state
# ---------------------------------------------------------------------------


@ai_bp.get("/v1/api/ai/state")
@ai_bp.get("/api/ai/state")
@require_auth
def get_ai_state():
    """返回当前 AI 对战状态。"""
    session_key = _get_ai_session_key()
    with runtime.AI_STATE_LOCK:
        session = runtime.get_ai_session(session_key)
        payload = _get_ai_state_payload(session)
    return jsonify(payload)


# ---------------------------------------------------------------------------
# POST /api/ai/reset
# ---------------------------------------------------------------------------


@ai_bp.post("/v1/api/ai/reset")
@ai_bp.post("/api/ai/reset")
@require_auth
def reset_ai_game():
    """重置 AI 对战状态，清空对局记录 ID。"""
    session_key = _get_ai_session_key()
    with runtime.AI_STATE_LOCK:
        session = runtime.reset_ai_session(session_key)
        payload = _get_ai_state_payload(session)
    return jsonify(
        {
            "ok": True,
            "message": "AI 对战已重置。",
            "state": payload,
        }
    )


# ---------------------------------------------------------------------------
# POST /api/ai/step
# ---------------------------------------------------------------------------


@ai_bp.post("/v1/api/ai/step")
@ai_bp.post("/api/ai/step")
@require_auth
def ai_step():
    """
    提交真人动作，后端统一生成 AI 动作并结算。

    请求体:
        {
            "human_move": "GI",       # 真人动作名（必需）
            "difficulty": "normal",   # easy | normal | hard（默认 normal）
            "human_seat": "p1"        # p1 | p2（默认 p1，AI 固定为另一侧）
        }

    返回:
        {
            "ok": true,
            "message": "...",
            "state": {...},
            "ai_move": "QI",
            "ai_move_label": "气",
            "difficulty": "normal",
            "human_seat": "p1",
            "ai_seat": "p2",
            "battle_id": "20260629000000000"
        }
    """
    request_started = time.perf_counter()

    # 1. 校验 JSON
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    human_move_name = data.get("human_move")
    difficulty = data.get("difficulty", "normal")
    human_seat = data.get("human_seat", "p1")

    # 2. 校验字段类型
    if not isinstance(human_move_name, str):
        return jsonify({"ok": False, "error": "必须提供字符串类型的 human_move。"}), 400

    if difficulty not in ("easy", "normal", "hard"):
        return jsonify(
            {"ok": False, "error": f"未知难度: {difficulty}。可选: easy, normal, hard"}
        ), 400

    if human_seat not in ("p1", "p2"):
        return jsonify(
            {"ok": False, "error": "human_seat 必须为 p1 或 p2。"}
        ), 400

    # 3. 解析动作名
    try:
        human_move = parse_move_name(human_move_name)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    human_player = 1 if human_seat == "p1" else 2
    ai_player = 2 if human_seat == "p1" else 1
    session_key = _get_ai_session_key()

    with runtime.AI_STATE_LOCK:
        session = runtime.get_ai_session(session_key)
        state = session.state

        # 4. 校验游戏未结束
        if state.winner is not None:
            return jsonify(
                {"ok": False, "error": "游戏已结束，请重置后再继续。"}
            ), 400

        if session.difficulty is not None and difficulty != session.difficulty:
            return jsonify(
                {
                    "ok": False,
                    "error": f"本局难度已锁定为 {session.difficulty}，请重置后再切换。",
                }
            ), 400

        if session.human_seat is not None and human_seat != session.human_seat:
            return jsonify(
                {
                    "ok": False,
                    "error": f"本局真人座位已锁定为 {session.human_seat}，请重置后再切换。",
                }
            ), 400

        # 5. 校验真人动作合法
        human_player_state = state.p1 if human_player == 1 else state.p2
        if not GameEngine.can_afford(human_player_state, human_move):
            return jsonify(
                {
                    "ok": False,
                    "error": f"动作 {human_move.value} 对当前玩家不合法。",
                }
            ), 400

        # 6. 复制回合开始状态，传给 AI（防作弊）
        state_for_ai = state.copy()

        # 7. AI 决策
        rng = random.Random()
        inference_started = time.perf_counter()
        try:
            ai_move = select_move(
                state_for_ai, ai_player, rng, {"difficulty": difficulty}
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        ai_inference_ms = round((time.perf_counter() - inference_started) * 1000, 4)

        # 8. 结算回合
        if human_player == 1:
            p1_move, p2_move = human_move, ai_move
        else:
            p1_move, p2_move = ai_move, human_move

        GameEngine.resolve_round(state, p1_move, p2_move)

        # 9. 对战记录
        human_username = get_current_username()
        human_uid = g.current_user.get("uid", -1) if hasattr(g, "current_user") else -1
        policy_type = policy_type_for_difficulty(difficulty)
        model_version = model_version_for_difficulty(difficulty)
        model_status = model_status_for_difficulty(difficulty)

        if session.battle_id is None:
            session.difficulty = difficulty
            session.human_seat = human_seat
            session.ai_seat = f"p{ai_player}"
            session.policy_type = policy_type

            # 参与者：P1=真人/AI, P2=AI/真人
            p1_entry = {
                "username": human_username if human_seat == "p1" else "ClapClap AI",
                "uid": human_uid if human_seat == "p1" else -2,
            }
            p2_entry = {
                "username": "ClapClap AI" if human_seat == "p1" else human_username,
                "uid": -2 if human_seat == "p1" else human_uid,
            }

            session.battle_id = create_battle(
                {"p1": p1_entry, "p2": p2_entry},
                mode="ai",
                rule_version="1.0",
            )

            # 写入 AI 元信息
            set_battle_metadata(session.battle_id, {
                "opponent_type": "ai",
                "ai_policy_type": policy_type,
                "ai_difficulty": difficulty,
                "ai_model_version": model_version,
                "ai_model_status": model_status,
                "ai_seat": f"p{ai_player}",
                "human_seat": human_seat,
                "action_space_size": ACTION_SPACE_SIZE,
                "action_space_fingerprint": get_action_space_fingerprint(),
                "observation_version": AI_OBSERVATION_VERSION,
            })

        # 记录本回合
        if state.history:
            round_data = state.history[-1].to_dict()
            round_data.update({
                "human_seat": human_seat,
                "ai_seat": f"p{ai_player}",
                "human_move": human_move.name,
                "ai_move": ai_move.name,
                "ai_difficulty": session.difficulty,
                "ai_policy_type": session.policy_type,
                "ai_model_version": model_version,
                "ai_model_status": model_status,
                "ai_inference_ms": ai_inference_ms,
            })
            record_round(session.battle_id, round_data)

        # 10. 终局处理
        if state.winner is not None:
            end_battle(session.battle_id, state.winner)

        session.touch()
        payload = _get_ai_state_payload(session)
        battle_id = session.battle_id

    return jsonify(
        {
            "ok": True,
            "message": "本回合已结算。",
            "state": payload,
            "ai_move": ai_move.name,
            "ai_move_label": ai_move.value,
            "difficulty": difficulty,
            "human_seat": human_seat,
            "ai_seat": f"p{ai_player}",
            "battle_id": battle_id,
            "ai_policy_type": session.policy_type,
            "ai_model_status": model_status,
            "ai_inference_ms": ai_inference_ms,
            "api_elapsed_ms": round((time.perf_counter() - request_started) * 1000, 4),
        }
    )
