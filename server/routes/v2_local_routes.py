"""
ClapClap 2.0 本地模拟对战 API。

提供 v2 引擎的本地多玩家对战接口：
  - 准备阶段：创建对局（设定人数和名称）
  - 对局阶段：提交动作、步进结算、提交决策
"""

from flask import Blueprint, jsonify, request

from app.v2.constants import Move
from app.v2.constants import (
    DECISION_TYPE_CONFLICT_RESOLVE,
    DECISION_TYPE_TARGET_SELECT,
    DECISION_TYPE_THREE_CHAIN_SELECT,
    STEP_ACTION_GAME_OVER,
    STEP_ACTION_REQUEST_DECISION,
    STEP_ACTION_ROUND_COMPLETE,
    SPEED_LAYER_NAMES,
)
from app.v2.game import GameEngineV2
from app.v2.models import (
    EventType,
    GameStateV2,
    PlayerStateV2,
    SpeedLayerEvent,
)
from app.v2.state_api import get_game_state_v2_payload
import server.runtime as runtime

v2_local_bp = Blueprint("v2_local", __name__)


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════

def _build_initial_state(player_count: int, names: list[str]) -> GameStateV2:
    """根据人数和名称创建初始 GameStateV2。"""
    players = []
    for i in range(player_count):
        pid = f"p{i + 1}"
        name = names[i] if i < len(names) else f"玩家{i + 1}"
        players.append(PlayerStateV2(
            player_id=pid,
            seat_index=i,
            username=name,
        ))
    return GameStateV2(players=players, max_players=player_count)


def _auto_advance(engine: GameEngineV2, result) -> dict:
    """如果引擎不需要玩家决策，自动推进到下一个决策点或完成。

    仅在本地模式使用——房间模式中决策由各玩家通过 Socket 提交。
    自动决策时向事件日志追加原因说明（决策记录由引擎内部 handler 负责）。
    """
    while result.action == STEP_ACTION_REQUEST_DECISION:
        layer = result.current_speed_layer
        layer_name = SPEED_LAYER_NAMES.get(layer, "")

        # 先生成默认决策
        default_decisions = GameEngineV2._make_default_decisions(result.decision_requests)

        # 为每个决策请求生成原因说明，写入速度层事件流
        for req in result.decision_requests:
            req_dict = req.to_dict() if hasattr(req, 'to_dict') else req
            dtype = req_dict.get("decision_type", "")
            player_id = req_dict.get("player_id", "")
            options = req_dict.get("options", [])
            split_count = req_dict.get("split_count", 1)

            player = engine.state.get_player(player_id)
            player_name = player.username if player else player_id

            valid_options = [o for o in options if (o.get("is_valid", True) if isinstance(o, dict) else o.is_valid)]
            target_options = [o for o in valid_options if (o.get("option_id", "") if isinstance(o, dict) else o.option_id) != ""]

            if dtype == DECISION_TYPE_TARGET_SELECT:
                if not target_options:
                    reason = f"自动决策 [{layer_name}]：{player_name} 无合法攻击目标，自动放空。"
                elif len(target_options) == 1:
                    t = target_options[0]
                    tname = t.get("label", "") if isinstance(t, dict) else t.label
                    reason = f"自动决策 [{layer_name}]：{player_name} 攻击 {tname}（唯一合法目标）。"
                else:
                    sel = target_options[:split_count]
                    names = ", ".join(
                        (s.get("label", "") if isinstance(s, dict) else s.label)
                        for s in sel
                    )
                    reason = f"自动决策 [{layer_name}]：{player_name} 默认攻击 {names}。"

            elif dtype == DECISION_TYPE_THREE_CHAIN_SELECT:
                chosen = valid_options[0] if valid_options else {"label": "?"}
                cname = chosen.get("label", "?") if isinstance(chosen, dict) else chosen.label
                reason = f"自动决策 [三连选人]：{player_name} 默认选择 {cname}。"

            elif dtype == DECISION_TYPE_CONFLICT_RESOLVE:
                chosen = valid_options[0] if valid_options else {"label": "默认"}
                cname = chosen.get("label", "?") if isinstance(chosen, dict) else chosen.label
                reason = f"自动决策 [{layer_name} 协商]：{player_name} 默认 {cname}。"

            else:
                reason = f"自动决策 [{layer_name}]：{player_name} 使用默认值。"

            # 追加到速度层事件流（供前端展示）
            engine.log.add_event(SpeedLayerEvent(
                event_type=EventType.RESOLVED,
                speed_layer=layer,
                source_player_id=player_id,
                detail=reason,
                data={"auto_decision": True, "decision_type": dtype},
            ))

        result = engine.continue_settlement(default_decisions)
    return result


# ═══════════════════════════════════════════════════════════════
# 获取状态
# ═══════════════════════════════════════════════════════════════

@v2_local_bp.get("/v2/api/local/state")
def get_state():
    """获取当前 v2 对局状态。"""
    with runtime.CURRENT_STATE_V2_LOCK:
        payload = get_game_state_v2_payload(runtime.CURRENT_STATE_V2, include_history=True)
        # 附加当前结算阶段信息
        if runtime.CURRENT_ENGINE_V2 is not None:
            payload["_engine_active"] = True
        else:
            payload["_engine_active"] = False
    return jsonify({"ok": True, "state": payload})


# ═══════════════════════════════════════════════════════════════
# 重置/开始新对局
# ═══════════════════════════════════════════════════════════════

@v2_local_bp.post("/v2/api/local/reset")
def reset_game():
    """创建新对局。

    Body (JSON):
        player_count: int  (2~6)
        names: [str, ...]  (玩家显示名列表)
    """
    data = request.get_json(silent=True) or {}
    player_count = data.get("player_count", 2)
    names = data.get("names", [])

    if not isinstance(player_count, int) or player_count < 2 or player_count > 6:
        return jsonify({"ok": False, "error": "player_count 必须在 2~6 之间。"}), 400

    if not isinstance(names, list):
        names = []

    with runtime.CURRENT_STATE_V2_LOCK:
        runtime.CURRENT_STATE_V2 = _build_initial_state(player_count, names)
        runtime.CURRENT_BATTLE_ID_V2 = None
        runtime.CURRENT_ENGINE_V2 = None
        payload = get_game_state_v2_payload(runtime.CURRENT_STATE_V2, include_history=True)
        payload["_engine_active"] = False

    return jsonify({
        "ok": True,
        "message": f"对局已创建，{player_count} 名玩家就位。",
        "state": payload,
    })


# ═══════════════════════════════════════════════════════════════
# 提交动作 + 开始结算
# ═══════════════════════════════════════════════════════════════

@v2_local_bp.post("/v2/api/local/step")
def step_game():
    """提交所有玩家的动作，开始步进式结算。

    Body (JSON):
        moves: {player_id: move_name, ...}
        auto_resolve: bool  (可选，默认 false；true 则自动通过所有决策)
    """
    data = request.get_json(silent=True) or {}
    moves_raw = data.get("moves", {})
    auto_resolve = data.get("auto_resolve", False)

    if not isinstance(moves_raw, dict) or len(moves_raw) == 0:
        return jsonify({"ok": False, "error": "moves 不能为空。"}), 400

    with runtime.CURRENT_STATE_V2_LOCK:
        state = runtime.CURRENT_STATE_V2

        if state.is_game_over():
            return jsonify({"ok": False, "error": "对局已结束，请重新开始。"}), 400

        # ── 解析动作 ──
        moves: dict[str, Move] = {}
        for pid, move_name in moves_raw.items():
            try:
                moves[pid] = Move[move_name]
            except KeyError:
                return jsonify({"ok": False, "error": f"未知动作名: {move_name}"}), 400

        # ── 验证所有存活玩家都提交了 ──
        alive_ids = {p.player_id for p in state.alive_players()}
        submitted_ids = set(moves.keys())
        if alive_ids != submitted_ids:
            missing = alive_ids - submitted_ids
            extra = submitted_ids - alive_ids
            msg_parts = []
            if missing:
                msg_parts.append(f"缺少: {', '.join(sorted(missing))}")
            if extra:
                msg_parts.append(f"多余(非存活): {', '.join(sorted(extra))}")
            return jsonify({"ok": False, "error": "动作集合与存活玩家不匹配。" + "；".join(msg_parts)}), 400

        # ── 合法性预检 ──
        for pid, move in moves.items():
            player = state.get_player(pid)
            if player is None or not player.is_alive():
                continue
            if not GameEngineV2.can_afford(player, move):
                return jsonify({
                    "ok": False,
                    "error": f"{player.username} 资源不足以使用 {move.value}。",
                }), 400

        # ── 开始结算 ──
        try:
            engine = GameEngineV2(state)
            result = engine.begin_settlement(moves)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return jsonify({"ok": False, "error": f"引擎结算异常: {exc}"}), 500

        # ── 保存引擎引用 ──
        runtime.CURRENT_ENGINE_V2 = engine

        # ── 自动推进（如不需要决策或 auto_resolve 为 true）──
        if auto_resolve or result.action != STEP_ACTION_REQUEST_DECISION:
            result = _auto_advance(engine, result)

        # ── 回合完成后处理 ──
        if result.action in (STEP_ACTION_ROUND_COMPLETE, STEP_ACTION_GAME_OVER):
            _handle_settlement_complete(state)
            runtime.CURRENT_ENGINE_V2 = None

        payload = get_game_state_v2_payload(state, include_history=True)
        payload["_engine_active"] = runtime.CURRENT_ENGINE_V2 is not None

    return jsonify({
        "ok": True,
        "settlement": result.to_dict() if hasattr(result, 'to_dict') else result,
        "state": payload,
    })


# ═══════════════════════════════════════════════════════════════
# 提交决策 + 继续结算
# ═══════════════════════════════════════════════════════════════

@v2_local_bp.post("/v2/api/local/decision")
def submit_decision():
    """提交决策，继续结算。

    Body (JSON):
        decisions: dict  格式取决于 decision_type
        auto_resolve: bool  (可选)
    """
    data = request.get_json(silent=True) or {}
    decisions = data.get("decisions", {})
    auto_resolve = data.get("auto_resolve", False)

    if not isinstance(decisions, dict):
        return jsonify({"ok": False, "error": "decisions 必须是字典。"}), 400

    with runtime.CURRENT_STATE_V2_LOCK:
        engine = runtime.CURRENT_ENGINE_V2
        if engine is None:
            return jsonify({"ok": False, "error": "当前没有进行中的结算。请先提交动作。"}), 400

        try:
            result = engine.continue_settlement(decisions)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            runtime.CURRENT_ENGINE_V2 = None
            return jsonify({"ok": False, "error": f"决策处理异常: {exc}"}), 500

        # ── 自动推进 ──
        if auto_resolve or result.action != STEP_ACTION_REQUEST_DECISION:
            result = _auto_advance(engine, result)

        # ── 完成处理 ──
        if result.action in (STEP_ACTION_ROUND_COMPLETE, STEP_ACTION_GAME_OVER):
            _handle_settlement_complete(runtime.CURRENT_STATE_V2)
            runtime.CURRENT_ENGINE_V2 = None

        payload = get_game_state_v2_payload(runtime.CURRENT_STATE_V2, include_history=True)
        payload["_engine_active"] = runtime.CURRENT_ENGINE_V2 is not None

    return jsonify({
        "ok": True,
        "settlement": result.to_dict() if hasattr(result, 'to_dict') else result,
        "state": payload,
    })


# ═══════════════════════════════════════════════════════════════
# 结算完成后的处理
# ═══════════════════════════════════════════════════════════════

def _handle_settlement_complete(state: GameStateV2) -> None:
    """回合/对局完成后记录对局。"""
    import server.runtime as rt

    # ── 创建对局记录（首次回合时）──
    if rt.CURRENT_BATTLE_ID_V2 is None:
        from app.battle_recorder import create_battle
        participants = {}
        seats = []
        for p in state.players:
            participants[p.player_id] = {
                "username": p.username,
                "uid": -1,  # 本地模式
                "seat_index": p.seat_index,
                "player_id": p.player_id,
                "is_host": False,
            }
            seats.append({
                "seat_index": p.seat_index,
                "player_id": p.player_id,
                "username": p.username,
                "uid": -1,
                "is_host": False,
            })
        rt.CURRENT_BATTLE_ID_V2 = create_battle(
            participants,
            rule_version="2.0",
            mode="local",
            seats=seats,
            host=None,
            room={
                "max_players": state.max_players,
            },
        )

    # ── 记录回合 ──
    if state.history:
        from app.battle_recorder import record_round
        latest_log = state.history[-1]
        record_round(rt.CURRENT_BATTLE_ID_V2, latest_log.to_dict())

    # ── 对局结束标记 ──
    if state.is_game_over():
        from app.battle_recorder import end_battle
        end_battle(rt.CURRENT_BATTLE_ID_V2, state.winner)
