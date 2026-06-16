from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app import users
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

    if new_password is not None:
        confirm = (data.get("confirm_password") or "")
        if new_password != confirm:
            return jsonify({"ok": False, "error": "两次输入的新密码不一致。"}), 400

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
