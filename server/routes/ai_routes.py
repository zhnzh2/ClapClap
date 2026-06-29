"""
ClapClap 1.0 AI 对战 API。

端点:
  GET  /api/ai/state  — 获取当前 AI 对战状态
  POST /api/ai/reset  — 重置 AI 对战
  POST /api/ai/step   — 提交真人动作 + AI 决策 + 结算
"""

from __future__ import annotations

import random

from flask import Blueprint, g, jsonify, request

from app.ai.engine import select_move
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


# ---------------------------------------------------------------------------
# GET /api/ai/state
# ---------------------------------------------------------------------------


@ai_bp.get("/api/ai/state")
@require_auth
def get_ai_state():
    """返回当前 AI 对战状态。"""
    with runtime.AI_STATE_LOCK:
        payload = get_game_state_payload(runtime.AI_STATE, include_history=True)
    return jsonify(payload)


# ---------------------------------------------------------------------------
# POST /api/ai/reset
# ---------------------------------------------------------------------------


@ai_bp.post("/api/ai/reset")
@require_auth
def reset_ai_game():
    """重置 AI 对战状态，清空对局记录 ID。"""
    with runtime.AI_STATE_LOCK:
        runtime.AI_STATE = runtime.AI_STATE.__class__()
        runtime.CURRENT_AI_BATTLE_ID = None
        payload = get_game_state_payload(runtime.AI_STATE, include_history=True)
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
            "difficulty": "normal"
        }
    """
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

    with runtime.AI_STATE_LOCK:
        state = runtime.AI_STATE

        # 4. 校验游戏未结束
        if state.winner is not None:
            return jsonify(
                {"ok": False, "error": "游戏已结束，请重置后再继续。"}
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
        ai_move = select_move(
            state_for_ai, ai_player, rng, {"difficulty": difficulty}
        )

        # 8. 结算回合
        if human_player == 1:
            p1_move, p2_move = human_move, ai_move
        else:
            p1_move, p2_move = ai_move, human_move

        GameEngine.resolve_round(state, p1_move, p2_move)

        # 9. 对战记录
        human_username = get_current_username()
        human_uid = g.current_user.get("uid", -1) if hasattr(g, "current_user") else -1

        if runtime.CURRENT_AI_BATTLE_ID is None:
            # 参与者：P1=真人/AI, P2=AI/真人
            p1_entry = {
                "username": human_username if human_seat == "p1" else "ClapClap AI",
                "uid": human_uid if human_seat == "p1" else -2,
            }
            p2_entry = {
                "username": "ClapClap AI" if human_seat == "p1" else human_username,
                "uid": -2 if human_seat == "p1" else human_uid,
            }

            runtime.CURRENT_AI_BATTLE_ID = create_battle(
                {"p1": p1_entry, "p2": p2_entry},
                mode="ai",
                rule_version="1.0",
            )

            # 写入 AI 元信息
            set_battle_metadata(runtime.CURRENT_AI_BATTLE_ID, {
                "opponent_type": "ai",
                "ai_policy_type": "heuristic" if difficulty != "easy" else "random",
                "ai_difficulty": difficulty,
                "ai_model_version": None,
                "ai_seat": f"p{ai_player}",
            })

        # 记录本回合
        if state.history:
            record_round(runtime.CURRENT_AI_BATTLE_ID, state.history[-1].to_dict())

        # 10. 终局处理
        if state.winner is not None:
            end_battle(runtime.CURRENT_AI_BATTLE_ID, state.winner)

        payload = get_game_state_payload(state, include_history=True)

    return jsonify(
        {
            "ok": True,
            "message": "本回合已结算。",
            "state": payload,
            "ai_move": ai_move.name,
            "ai_move_label": ai_move.value,
            "difficulty": difficulty,
        }
    )
