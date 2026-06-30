"""
认证中间件。

提供 require_auth 装饰器和获取当前用户名的辅助函数。
受保护路由可通过 `g.current_user` 获取当前登录用户。
"""

from functools import wraps

from flask import Blueprint, g, jsonify, request

from app.users import get_user_by_session_token


def _extract_session_token() -> str | None:
    """从请求中提取 session token（只接受 header / JSON body）。"""
    # Header
    token = request.headers.get("X-Session-Token", "").strip()
    if token:
        return token

    # JSON body
    data = request.get_json(silent=True)
    if data and isinstance(data.get("session_token"), str):
        token = data["session_token"].strip()
        if token:
            return token

    return None


def require_auth(f):
    """装饰器：要求请求携带有效的 session token。将用户信息存入 g.current_user。"""

    @wraps(f)
    def decorated(*args, **kwargs):
        login_path = "/v2/login" if request.path.startswith("/v2/") else "/v1/login"
        token = _extract_session_token()
        if not token:
            return jsonify({"ok": False, "error": "请先登录。", "redirect": login_path}), 401

        user = get_user_by_session_token(token)
        if user is None:
            return jsonify({"ok": False, "error": "登录已过期，请重新登录。", "redirect": login_path}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def get_current_username() -> str:
    """获取当前请求的用户名（由 require_auth 保证 g.current_user 存在）。"""
    user = getattr(g, "current_user", None)
    if user:
        return user.get("username", "")
    return ""
