from flask import Blueprint, jsonify, request

from app.matchmaking import (
    enqueue_or_match,
    get_match_status,
    pop_player_match_result,
    get_player_match_state,
    cancel_match,
)
from server.runtime import run_periodic_cleanup

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

    try:
        run_periodic_cleanup()
        result = enqueue_or_match(player_name.strip(), player_token.strip())
        from server.socket_events import emit_match_status
        emit_match_status()

        if result["matched"]:
            return jsonify({
                "ok": True,
                "matched": True,
                "message": "匹配成功，已进入房间。" if not result.get("already_in_room") else "你已经在房间中，正在返回。",
                "room_id": result["room_id"],
                "p1_name": result["p1_name"],
                "p2_name": result["p2_name"],
                "seat": result["seat"],
                "room_player_token": result.get("room_player_token"),
                "already_in_room": result.get("already_in_room", False),
            }), 200

        return jsonify({
            "ok": True,
            "matched": False,
            "message": "已进入匹配队列，等待另一位玩家。",
            "waiting_player": result["waiting_player"],
        }), 200
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"匹配接口内部报错：{exc}"}), 500


@match_bp.get("/api/match/status")
def api_match_status():
    run_periodic_cleanup()
    status = get_match_status()
    return jsonify({"ok": True, "status": status}), 200


@match_bp.get("/api/match/me")
def api_match_me():
    player_token = request.args.get("player_token", type=str)
    if player_token is None or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    run_periodic_cleanup()
    state = get_player_match_state(player_token.strip())
    return jsonify({"ok": True, "state": state}), 200


@match_bp.post("/api/match/cancel")
def api_match_cancel():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    player_token = data.get("player_token")
    if not isinstance(player_token, str) or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    run_periodic_cleanup()
    result = cancel_match(player_token.strip())
    from server.socket_events import emit_match_status
    emit_match_status()
    return jsonify(result), 200


@match_bp.get("/api/match/result")
def api_match_result():
    player_token = request.args.get("player_token", type=str)
    if player_token is None or not player_token.strip():
        return jsonify({"ok": False, "error": "player_token 不能为空。"}), 400

    result = pop_player_match_result(player_token.strip())
    return jsonify({
        "ok": True,
        "matched": result["matched"],
        "room_id": result["room_id"],
        "seat": result["seat"],
        "room_player_token": result["room_player_token"],
    }), 200