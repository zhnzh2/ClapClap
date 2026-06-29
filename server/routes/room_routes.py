from flask import Blueprint, jsonify, request

from server.services.room_service import (
    create_room_service,
    join_room_service,
    get_room_service,
    submit_room_move_service,
    reset_room_service,
    cancel_room_move_service,
    leave_room_service,
)
from server.auth_middleware import require_auth, get_current_username

room_bp = Blueprint("room", __name__)


@room_bp.post("/v1/api/rooms")
@require_auth
def api_create_room():
    player_name = get_current_username()
    data = request.get_json(silent=True) or {}
    rule_version = data.get("rule_version", "1.0")
    if rule_version not in ("1.0", "2.0"):
        return jsonify({"ok": False, "error": f"不支持的规则版本: {rule_version}"}), 400
    result = create_room_service(player_name, rule_version=rule_version)
    return jsonify(result)


@room_bp.post("/v1/api/rooms/<room_id>/join")
@require_auth
def api_join_room(room_id: str):
    player_name = get_current_username()
    try:
        result = join_room_service(room_id, player_name)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@room_bp.get("/v1/api/rooms/<room_id>")
def api_get_room(room_id: str):
    player_token = request.args.get("player_token", type=str)
    result, status_code = get_room_service(room_id, player_token)
    return jsonify(result), status_code


@room_bp.post("/v1/api/rooms/<room_id>/step")
def api_room_step(room_id: str):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    move_name = data.get("move_name")

    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    if not isinstance(move_name, str):
        return jsonify({"ok": False, "error": "move_name 必须是字符串。"}), 400

    result, status_code = submit_room_move_service(
        room_id,
        player_token.strip(),
        move_name,
    )
    return jsonify(result), status_code


@room_bp.post("/v1/api/rooms/<room_id>/reset")
def api_room_reset(room_id: str):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = reset_room_service(room_id, player_token.strip())
    return jsonify(result), status_code

@room_bp.post("/v1/api/rooms/<room_id>/cancel-step")
def api_room_cancel_step(room_id: str):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = cancel_room_move_service(room_id, player_token.strip())
    return jsonify(result), status_code

@room_bp.post("/v1/api/rooms/<room_id>/leave")
def api_leave_room(room_id: str):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = leave_room_service(room_id, player_token.strip())
    return jsonify(result), status_code