from flask import Blueprint, jsonify, request

from services.match_service import (
    join_match_service,
    get_match_status_service,
    get_my_match_state_service,
    cancel_match_service,
    pop_match_result_service,
)

match_bp = Blueprint("match", __name__)


@match_bp.post("/api/match/join")
def api_match_join():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_name = data.get("player_name")
    player_token = data.get("player_token")

    if not isinstance(player_name, str) or not player_name.strip():
        return jsonify({"ok": False, "error": "player_name 不能为空。"}), 400

    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = join_match_service(
        player_name.strip(),
        player_token.strip(),
    )
    return jsonify(result), status_code


@match_bp.get("/api/match/status")
def api_match_status():
    result, status_code = get_match_status_service()
    return jsonify(result), status_code


@match_bp.get("/api/match/me")
def api_match_me():
    player_token = request.args.get("player_token", type=str)
    if player_token is None or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = get_my_match_state_service(player_token.strip())
    return jsonify(result), status_code


@match_bp.post("/api/match/cancel")
def api_match_cancel():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = cancel_match_service(player_token.strip())
    return jsonify(result), status_code


@match_bp.get("/api/match/result")
def api_match_result():
    player_token = request.args.get("player_token", type=str)
    if player_token is None or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result, status_code = pop_match_result_service(player_token.strip())
    return jsonify(result), status_code