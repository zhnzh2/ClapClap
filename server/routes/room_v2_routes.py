"""
ClapClap 2.0 房间 API 路由。

与 1.0 (server/routes/room_routes.py) 完全独立。
路由前缀: /api/v2/rooms
"""

from flask import Blueprint, jsonify, request

from server.services.room_v2_service import (
    create_room_v2_service,
    join_room_v2_service,
    get_room_v2_service,
    set_ready_service,
    start_game_service,
    submit_move_v2_service,
    leave_room_v2_service,
    rematch_vote_service,
    change_seat_service,
)
from server.auth_middleware import require_auth, get_current_username
from app.v2.constants import MAX_PLAYERS, MIN_PLAYERS
from app.v2.room import START_HOST, START_ALL_READY, START_FULL
from app.v2.room_manager import get_room_v2

room_v2_bp = Blueprint("room_v2", __name__)


# ═══════════════════════════════════════════════════════
# 创建房间
# ═══════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms")
@require_auth
def api_create_room_v2():
    """创建 2.0 多人房间。"""
    player_name = get_current_username()
    data = request.get_json(silent=True) or {}

    max_players = data.get("max_players", MAX_PLAYERS)
    if not isinstance(max_players, int) or max_players < MIN_PLAYERS or max_players > MAX_PLAYERS:
        return jsonify({
            "ok": False,
            "error": f"max_players 必须在 {MIN_PLAYERS}~{MAX_PLAYERS} 之间。",
        }), 400

    min_players = data.get("min_players", MIN_PLAYERS)
    if not isinstance(min_players, int) or min_players < MIN_PLAYERS or min_players > max_players:
        return jsonify({
            "ok": False,
            "error": f"min_players 必须在 {MIN_PLAYERS}~{max_players} 之间。",
        }), 400

    start_condition = data.get("start_condition", START_HOST)
    if start_condition not in (START_HOST, START_ALL_READY, START_FULL):
        return jsonify({
            "ok": False,
            "error": f"start_condition 必须是 {START_HOST}/{START_ALL_READY}/{START_FULL} 之一。",
        }), 400

    allow_spectate = data.get("allow_spectate", True)
    if not isinstance(allow_spectate, bool):
        allow_spectate = True

    public = data.get("public", False)
    if not isinstance(public, bool):
        public = False

    password = data.get("password")
    if password is not None and (not isinstance(password, str) or not password.strip()):
        password = None

    result = create_room_v2_service(
        player_name,
        max_players=max_players,
        min_players=min_players,
        start_condition=start_condition,
        allow_spectate=allow_spectate,
        public=public,
        password=password,
    )
    return jsonify(result)


# ═══════════════════════════════════════════════════════════
# 加入房间
# ═══════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/join")
@require_auth
def api_join_room_v2(room_id: str):
    """加入 2.0 房间（参战或观战）。"""
    player_name = get_current_username()
    data = request.get_json(silent=True) or {}
    as_spectator = data.get("as_spectator", False)
    seat_index = data.get("seat_index")

    try:
        result = join_room_v2_service(
            room_id, player_name,
            as_spectator=as_spectator,
            seat_index=seat_index,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


# ═══════════════════════════════════════════════════════════
# 获取房间状态
# ═══════════════════════════════════════════════════════════

@room_v2_bp.get("/api/v2/rooms/<room_id>")
def api_get_room_v2(room_id: str):
    """获取 2.0 房间状态。"""
    player_token = request.args.get("player_token", type=str)
    result, status_code = get_room_v2_service(room_id, player_token)
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════
# 准备
# ═══════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/ready")
def api_set_ready(room_id: str):
    """切换准备状态。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    ready = data.get("ready", True)
    if not isinstance(ready, bool):
        ready = True

    result, status_code = set_ready_service(room_id, player_token.strip(), ready)
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════
# 更换席位
# ═══════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/change-seat")
def api_change_seat(room_id: str):
    """更换席位号（仅限 lobby 阶段）。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    new_seat_index = data.get("seat_index")
    if not isinstance(new_seat_index, int):
        return jsonify({"ok": False, "error": "seat_index 必须是整数。"}), 400

    result, status_code = change_seat_service(room_id, player_token.strip(), new_seat_index)
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════
# 开始对局
# ═══════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/start")
def api_start_game(room_id: str):
    """房主发起开始对局。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = start_game_service(room_id, player_token.strip())
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════
# 提交动作
# ═══════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/step")
def api_submit_move_v2(room_id: str):
    """提交本回合动作。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    move_name = data.get("move_name")
    if not isinstance(move_name, str):
        return jsonify({"ok": False, "error": "move_name 必须是字符串。"}), 400

    result, status_code = submit_move_v2_service(
        room_id,
        player_token.strip(),
        move_name,
    )
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════
# 退出房间
# ═══════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/leave")
def api_leave_room_v2(room_id: str):
    """退出 2.0 房间。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = leave_room_v2_service(room_id, player_token.strip())
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════
# 重赛投票
# ═══════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/rematch")
def api_rematch_vote(room_id: str):
    """重赛投票。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    vote = data.get("vote", True)
    if not isinstance(vote, bool):
        vote = True

    result, status_code = rematch_vote_service(room_id, player_token.strip(), vote)
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════════
# Step 6：提交结算决策
# ═══════════════════════════════════════════════════════════════

@room_v2_bp.post("/api/v2/rooms/<room_id>/decision")
def submit_decision_v2(room_id: str):
    """提交结算中的决策（目标选择、冲突协商等）。

    Body (JSON):
        player_token: str    — 玩家身份 token
        decisions: dict      — 决策数据

    decisions 格式示例:
        # 目标选择（非拆分技能）
        {"p1": ["p3"]}
        # 目标选择（拆分技能）
        {"p1": ["p3", "p4"]}  # 双吃2段，或黑洞3段
        # 冲突协商（多攻少，被攻击者选择）
        {"p3": "p1"}
        # 冲突协商（互攻）
        {"p1": "p2", "p2": ""}  # p1坚持攻击p2，p2放空
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    decisions = data.get("decisions", {})
    if not isinstance(decisions, dict):
        return jsonify({"ok": False, "error": "decisions 必须是字典。"}), 400

    from server.services.room_v2_service import submit_decision_v2_service
    result, status_code = submit_decision_v2_service(
        room_id, player_token.strip(), decisions,
    )
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════════
# Step 6：获取当前决策请求（方便前端轮询）
# ═══════════════════════════════════════════════════════════════

@room_v2_bp.get("/api/v2/rooms/<room_id>/decisions")
def get_pending_decisions_v2(room_id: str):
    """获取当前待处理的决策请求列表。

    前端可以在 `settlement_progress_v2` 事件之外轮询此端点。
    """
    room = get_room_v2(room_id)
    if room is None:
        return jsonify({
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }), 404

    if room.game_state is None:
        return jsonify({
            "ok": True,
            "decision_requests": [],
            "decision_requests_summary": [],
            "phase": "",
        }), 200

    player_token = request.args.get("player_token", type=str)
    requester_player_id = None
    if player_token:
        seat = room.get_seat_by_token(player_token.strip())
        if seat is None:
            return jsonify({"ok": False, "error": "身份无效。"}), 403
        requester_player_id = seat.player_id

    decision_requests = []
    decision_requests_summary = []
    for r in room.game_state.current_decision_requests:
        if hasattr(r, 'to_dict'):
            item = r.to_dict()
        else:
            item = r

        decision_requests_summary.append({
            "decision_id": item.get("decision_id", ""),
            "decision_type": item.get("decision_type", ""),
            "speed_layer": item.get("speed_layer", 0),
            "player_id": item.get("player_id", ""),
            "split_count": item.get("split_count", 1),
            "negotiation_round": item.get("negotiation_round", 0),
        })

        if requester_player_id and item.get("player_id") == requester_player_id:
            decision_requests.append(item)

    return jsonify({
        "ok": True,
        "phase": room.game_state.phase,
        "sub_phase": room.game_state.sub_phase,
        "current_speed_layer": room.game_state.current_speed_layer,
        "decision_requests": decision_requests,
        "decision_requests_summary": decision_requests_summary,
    }), 200
