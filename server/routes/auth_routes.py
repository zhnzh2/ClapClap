from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app import users
from app.battle_recorder import read_battle
from server.auth_middleware import require_auth

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/api/auth/register")
def api_register():
    """注册：用户名、密码、确认密码、介绍信（可选）。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "")
    confirm_password = (data.get("confirm_password") or "")
    intro = (data.get("intro") or "").strip()

    if not username:
        return jsonify({"ok": False, "error": "用户名不能为空。"}), 400
    if not password:
        return jsonify({"ok": False, "error": "密码不能为空。"}), 400
    if password != confirm_password:
        return jsonify({"ok": False, "error": "两次输入的密码不一致。"}), 400

    result = users.register(username, password, intro, verified="0", role="user")
    if not result["ok"]:
        return jsonify(result), 400

    # 注册成功后自动登录
    login_result = users.login(username, password)
    if login_result["ok"]:
        result["session_token"] = login_result["session_token"]

    return jsonify(result), 201


@auth_bp.post("/api/auth/login")
def api_login():
    """登录：用户名 + 密码。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "error": "用户名和密码不能为空。"}), 400

    result = users.login(username, password)
    if not result["ok"]:
        return jsonify(result), 401

    return jsonify(result), 200


@auth_bp.post("/api/auth/guest")
def api_guest():
    """访客登录：一键创建访客账号并自动登录。"""
    result = users.guest_register()
    if not result["ok"]:
        return jsonify(result), 500

    # 访客自动登录（默认密码 ClapClap）
    default_password = "ClapClap"
    username = result["user"]["username"]
    login_result = users.login(username, default_password)
    if login_result["ok"]:
        result["session_token"] = login_result["session_token"]

    result["default_password"] = default_password
    return jsonify(result), 201


@auth_bp.post("/api/auth/logout")
def api_logout():
    """登出。"""
    data = request.get_json(silent=True) or {}
    token = data.get("session_token") or request.headers.get("X-Session-Token", "")
    users.logout_token(token.strip())
    return jsonify({"ok": True, "message": "已登出。"}), 200


@auth_bp.get("/api/auth/me")
@require_auth
def api_me():
    """获取当前登录用户信息。"""
    return jsonify({
        "ok": True,
        "user": g.current_user,
    }), 200


@auth_bp.post("/api/auth/update")
@require_auth
def api_update():
    """修改账号信息：用户名、密码、介绍信（至少一个）。"""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "请求体必须是 JSON。"}), 400

    uid = g.current_user["uid"]

    new_username = data.get("username")
    new_password = data.get("password")
    new_intro = data.get("intro")

    if new_username is not None and not isinstance(new_username, str):
        return jsonify({"ok": False, "error": "用户名必须是字符串。"}), 400
    if new_password is not None and not isinstance(new_password, str):
        return jsonify({"ok": False, "error": "密码必须是字符串。"}), 400
    if new_intro is not None and not isinstance(new_intro, str):
        return jsonify({"ok": False, "error": "介绍信必须是字符串。"}), 400

    if new_password is not None:
        confirm = (data.get("confirm_password") or "")
        if new_password != confirm:
            return jsonify({"ok": False, "error": "两次输入的新密码不一致。"}), 400
        current_password = data.get("current_password") or ""
        if not isinstance(current_password, str):
            return jsonify({"ok": False, "error": "当前密码必须是字符串。"}), 400
        if not current_password:
            return jsonify({"ok": False, "error": "请输入当前密码。"}), 400
        if not users.verify_password(uid, current_password):
            return jsonify({"ok": False, "error": "当前密码不正确。"}), 403

    if new_username is None and new_password is None and new_intro is None:
        return jsonify({"ok": False, "error": "至少需要修改一项。"}), 400

    result = users.update_user(
        uid,
        username=new_username.strip() if isinstance(new_username, str) else None,
        password=new_password if isinstance(new_password, str) else None,
        intro=new_intro.strip() if isinstance(new_intro, str) else None,
    )

    if not result["ok"]:
        return jsonify(result), 400

    return jsonify(result), 200


@auth_bp.post("/api/auth/delete")
@require_auth
def api_delete():
    """注销账号。"""
    uid = g.current_user["uid"]
    if uid == 0:
        return jsonify({"ok": False, "error": "admin 账号不可注销。"}), 403
    users.logout_token(
        (request.headers.get("X-Session-Token") or "").strip()
    )
    users.delete_user(uid)
    return jsonify({"ok": True, "message": "账号已注销。"}), 200


# ── 管理员接口 ────────────────────────────────────────────────

@auth_bp.get("/api/admin/users")
@require_auth
def api_admin_users():
    """管理员查看所有用户列表。"""
    if not users.is_admin(g.current_user):
        return jsonify({"ok": False, "error": "权限不足。"}), 403

    all_users = users.get_all_users()
    return jsonify({"ok": True, "users": all_users}), 200


@auth_bp.post("/api/admin/verify/<int:uid>")
@require_auth
def api_admin_verify(uid: int):
    """管理员验证指定用户。"""
    if not users.is_admin(g.current_user):
        return jsonify({"ok": False, "error": "权限不足。"}), 403

    if not users.user_exists(uid):
        return jsonify({"ok": False, "error": "用户不存在。"}), 404

    users.verify_user(uid)
    return jsonify({"ok": True, "message": f"用户 {uid} 已验证。"}), 200


@auth_bp.post("/api/admin/delete/<int:uid>")
@require_auth
def api_admin_delete(uid: int):
    """管理员注销指定用户。"""
    if not users.is_admin(g.current_user):
        return jsonify({"ok": False, "error": "权限不足。"}), 403

    if uid == 0:
        return jsonify({"ok": False, "error": "不能注销 admin 账号。"}), 403

    if not users.user_exists(uid):
        return jsonify({"ok": False, "error": "用户不存在。"}), 404

    users.delete_user(uid)
    return jsonify({"ok": True, "message": f"用户 {uid} 已注销。"}), 200


# ── 用户公开信息接口 ────────────────────────────────────────────

@auth_bp.get("/api/user/<int:uid>")
@require_auth
def api_get_user(uid: int):
    """获取用户公开信息。"""
    user = users.get_user_by_uid(uid)
    if user is None:
        return jsonify({"ok": False, "error": "用户不存在。"}), 404
    return jsonify({"ok": True, "user": user}), 200


@auth_bp.get("/api/user/<int:uid>/battles")
@require_auth
def api_user_battles(uid: int):
    """获取用户参与的对局列表（摘要）。"""
    if not users.user_exists(uid):
        return jsonify({"ok": False, "error": "用户不存在。"}), 404

    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = min(max(limit or 50, 1), 100)
    offset = max(offset or 0, 0)
    battle_ids, total = users.get_user_battle_page(uid, limit, offset)
    battles: list[dict] = []

    for bid in battle_ids:
        data = read_battle(bid)
        if data is None:
            continue

        participants = data.get("participants", {})
        p1 = participants.get("p1", {})
        p2 = participants.get("p2", {})

        # 判断当前用户是哪一方
        my_seat = None
        opponent = None
        if p1.get("uid") == uid:
            my_seat = "p1"
            opponent = p2.get("username", "?")
        elif p2.get("uid") == uid:
            my_seat = "p2"
            opponent = p1.get("username", "?")

        # 判断结果
        winner = data.get("winner")
        result = "unknown"
        if winner is not None and my_seat is not None:
            if winner == 0:
                result = "draw"
            elif (winner == 1 and my_seat == "p1") or (winner == 2 and my_seat == "p2"):
                result = "win"
            else:
                result = "loss"
        elif data.get("end_time") is None:
            result = "ongoing"

        battles.append({
            "battle_id": bid,
            "start_time": data.get("start_time", ""),
            "end_time": data.get("end_time"),
            "p1_name": p1.get("username", "?"),
            "p2_name": p2.get("username", "?"),
            "opponent": opponent or "?",
            "result": result,
            "round_count": len(data.get("rounds", [])),
            "winner": winner,
        })

    next_offset = offset + len(battle_ids)
    return jsonify({
        "ok": True,
        "battles": battles,
        "total": total,
        "has_more": next_offset < total,
        "next_offset": next_offset,
    }), 200


@auth_bp.get("/api/battles/<battle_id>")
@require_auth
def api_battle_detail(battle_id: str):
    """获取单个对局的完整记录。"""
    data = read_battle(battle_id)
    if data is None:
        return jsonify({"ok": False, "error": "对局不存在。"}), 404
    return jsonify({"ok": True, "battle": data}), 200
