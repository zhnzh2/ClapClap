"""
ClapClap 2.0 匹配 API 路由。

与 1.0 (server/routes/match_routes.py) 完全独立。
路由前缀: /api/v2/match
"""

from flask import Blueprint, jsonify, request

from app.v2.matchmaking import (
    enqueue_v2,
    cancel_match_v2,
    get_queue_status_v2,
    get_player_match_state_v2,
    cleanup_expired_match_v2,
)
from app.v2.constants import MAX_PLAYERS, MIN_PLAYERS
from server.auth_middleware import require_auth, get_current_username

match_v2_bp = Blueprint("match_v2", __name__)


@match_v2_bp.post("/api/v2/match/join")
@require_auth
def api_match_v2_join():
    """加入 v2 匹配队列。"""
    player_name = get_current_username()
    data = request.get_json(silent=True) or {}
    player_token = data.get("player_token")

    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    preferred_players = data.get("preferred_players", 4)
    if (
        not isinstance(preferred_players, int)
        or preferred_players < MIN_PLAYERS
        or preferred_players > MAX_PLAYERS
    ):
        return jsonify({"ok": False, "error": f"preferred_players 必须在 {MIN_PLAYERS}~{MAX_PLAYERS} 之间。"}), 400

    try:
        cleanup_expired_match_v2()
        result = enqueue_v2(player_name.strip(), player_token.strip(), preferred_players)

        if result["matched"]:
            return jsonify({
                "ok": True,
                "matched": True,
                "message": result.get("message", "匹配成功！"),
                "room_id": result["room_id"],
                "seat_index": result.get("seat_index"),
                "room_player_token": result.get("room_player_token"),
            }), 200

        return jsonify({
            "ok": True,
            "matched": False,
            "message": result.get("message", "已加入匹配队列。"),
            "queue_size": result.get("queue_size", 1),
        }), 200
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"匹配接口内部报错：{exc}"}), 500


@match_v2_bp.get("/api/v2/match/status")
def api_match_v2_status():
    """获取 v2 匹配队列全局状态。"""
    cleanup_expired_match_v2()
    status = get_queue_status_v2()
    return jsonify({"ok": True, "status": status}), 200


@match_v2_bp.get("/api/v2/match/me")
def api_match_v2_me():
    """获取当前玩家的 v2 匹配状态。"""
    player_token = request.args.get("player_token", type=str)
    if not player_token or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    cleanup_expired_match_v2()
    state = get_player_match_state_v2(player_token.strip())
    return jsonify({"ok": True, "state": state}), 200


@match_v2_bp.post("/api/v2/match/cancel")
def api_match_v2_cancel():
    """取消 v2 匹配。"""
    data = request.get_json(silent=True) or {}
    player_token = data.get("player_token")

    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    cleanup_expired_match_v2()
    result = cancel_match_v2(player_token.strip())
    return jsonify(result), 200
