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
