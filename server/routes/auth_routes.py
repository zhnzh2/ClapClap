from __future__ import annotations

import io
import json
import time
import zipfile
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, redirect, render_template, request, send_file

from app import users
from app.battle_recorder import read_battle
from server.auth_middleware import require_auth

auth_bp = Blueprint("auth", __name__)
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 8


def _rate_limit_key(username: str) -> str:
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = forwarded_for or request.remote_addr or "unknown"
    return f"{ip}:{username.lower()}"


def _is_login_rate_limited(username: str) -> bool:
    global _LOGIN_ATTEMPTS
    now = time.time()
    cutoff = now - _LOGIN_WINDOW_SECONDS
    key = _rate_limit_key(username)
    attempts = [ts for ts in _LOGIN_ATTEMPTS.get(key, []) if ts >= cutoff]
    if attempts:
        _LOGIN_ATTEMPTS[key] = attempts
    else:
        _LOGIN_ATTEMPTS.pop(key, None)
    # 定期清理过期条目，避免长期运行内存缓慢增长
    if len(_LOGIN_ATTEMPTS) > 2000:
        _LOGIN_ATTEMPTS = {k: [ts for ts in v if ts >= cutoff] for k, v in _LOGIN_ATTEMPTS.items()}
        _LOGIN_ATTEMPTS = {k: v for k, v in _LOGIN_ATTEMPTS.items() if v}
    return len(attempts) >= _LOGIN_MAX_ATTEMPTS


def _record_failed_login(username: str) -> None:
    key = _rate_limit_key(username)
    _LOGIN_ATTEMPTS.setdefault(key, []).append(time.time())


def _clear_failed_logins(username: str) -> None:
    _LOGIN_ATTEMPTS.pop(_rate_limit_key(username), None)


@auth_bp.get("/login")
def legacy_login_page():
    return redirect("/v1/login")


@auth_bp.get("/v1/login")
@auth_bp.get("/v2/login")
def login_page():
    version = "v2" if request.path.startswith("/v2/") else "v1"
    return render_template("login.html", version=version)


def _get_participant_player_id(participants: dict, uid: int) -> str | None:
    for player_id, info in participants.items():
        if info.get("uid") == uid:
            return player_id
    return None


def _latest_v2_rank(data: dict, player_id: str | None):
    if not player_id:
        return None

    final_result = data.get("final_result", {}) or {}
    for item in final_result.get("rankings", []) or []:
        if item.get("player_id") == player_id:
            return item.get("rank")

    for round_data in reversed(data.get("rounds", []) or []):
        result = round_data.get("result", {}) or {}
        rank_updates = result.get("rank_updates") or round_data.get("rank_updates") or {}
        if player_id in rank_updates:
            return rank_updates.get(player_id)
    return None


def _v2_is_winner(data: dict, player_id: str | None) -> bool:
    if not player_id:
        return False
    final_result = data.get("final_result", {}) or {}
    winner = final_result.get("winner", data.get("winner"))
    if winner is not None:
        return str(winner) == str(player_id)
    return _latest_v2_rank(data, player_id) == 1 and data.get("end_time") is not None


def _is_ai_battle(data: dict) -> bool:
    return data.get("mode") == "ai" or data.get("opponent_type") == "ai"


def _battle_mode_bucket(data: dict) -> str:
    rule_version = str(data.get("rule_version", "1.0"))
    if rule_version.startswith("2."):
        return "v2"
    if _is_ai_battle(data):
        return "ai"
    return str(data.get("mode") or "v1")


def _v1_user_seat(data: dict, uid: int) -> str | None:
    participants = data.get("participants", {}) or {}
    p1 = participants.get("p1", {}) or {}
    p2 = participants.get("p2", {}) or {}
    if p1.get("uid") == uid:
        return "p1"
    if p2.get("uid") == uid:
        return "p2"
    return None


def _battle_result_for_uid(data: dict, uid: int) -> str:
    rule_version = str(data.get("rule_version", "1.0"))
    if rule_version.startswith("2."):
        participants = data.get("participants", {}) or {}
        player_id = _get_participant_player_id(participants, uid)
        if not data.get("end_time"):
            return "ongoing"
        return "win" if _v2_is_winner(data, player_id) else "loss"

    my_seat = _v1_user_seat(data, uid)
    winner = data.get("winner")
    if winner is not None and my_seat is not None:
        if winner == 0:
            return "draw"
        if (winner == 1 and my_seat == "p1") or (winner == 2 and my_seat == "p2"):
            return "win"
        return "loss"
    if data.get("end_time") is None:
        return "ongoing"
    return "unknown"


def _battle_filters_from_request() -> dict:
    return {
        "mode": (request.args.get("mode") or "all").strip().lower(),
        "result": (request.args.get("result") or "all").strip().lower(),
        "difficulty": (request.args.get("difficulty") or "all").strip().lower(),
        "q": (request.args.get("q") or "").strip().lower(),
    }


def _battle_matches_filters(data: dict, uid: int, filters: dict) -> bool:
    mode_filter = filters.get("mode") or "all"
    result_filter = filters.get("result") or "all"
    difficulty_filter = filters.get("difficulty") or "all"
    keyword = filters.get("q") or ""

    bucket = _battle_mode_bucket(data)
    if mode_filter != "all":
        if mode_filter == "v1":
            if str(data.get("rule_version", "1.0")).startswith("2.") or _is_ai_battle(data):
                return False
        elif mode_filter != bucket and mode_filter != data.get("mode"):
            return False

    if result_filter != "all":
        result = _battle_result_for_uid(data, uid)
        if result_filter == "completed":
            if data.get("end_time") is None:
                return False
        elif result != result_filter:
            return False

    if difficulty_filter != "all":
        if (data.get("ai_difficulty") or "").lower() != difficulty_filter:
            return False

    if keyword:
        participants = data.get("participants", {}) or {}
        haystack_parts = [
            str(data.get("battle_id", "")),
            str(data.get("mode_label", "")),
            str(data.get("ai_difficulty", "")),
            str(data.get("ai_policy_type", "")),
        ]
        haystack_parts.extend(str(info.get("username", "")) for info in participants.values())
        if keyword not in " ".join(haystack_parts).lower():
            return False

    return True


def _filtered_user_battle_ids(uid: int, filters: dict) -> list[str]:
    filtered: list[str] = []
    for bid in users.get_user_battle_ids(uid):
        data = read_battle(bid)
        if data is None:
            continue
        if _battle_matches_filters(data, uid, filters):
            filtered.append(bid)
    return filtered


def _summarize_user_battle(uid: int, bid: str, data: dict) -> dict | None:
    rule_version = str(data.get("rule_version", "1.0"))
    participants = data.get("participants", {})
    round_count = len(data.get("rounds", []))

    if rule_version.startswith("2."):
        final_result = data.get("final_result", {})
        rankings = final_result.get("rankings", [])
        my_player_id = _get_participant_player_id(participants, uid)
        my_rank = None
        is_winner = False
        for r in rankings:
            if participants.get(r.get("player_id", ""), {}).get("uid") == uid:
                my_rank = r.get("rank")
                is_winner = r.get("is_winner", False)
                break
        if my_rank is None:
            my_rank = _latest_v2_rank(data, my_player_id)
            is_winner = _v2_is_winner(data, my_player_id)

        participant_names = [
            p.get("username", "?") for p in participants.values()
        ]

        return {
            "battle_id": bid,
            "rule_version": rule_version,
            "start_time": data.get("start_time", ""),
            "end_time": data.get("end_time"),
            "mode": data.get("mode"),
            "mode_label": data.get("mode_label", ""),
            "player_count": len(participants),
            "my_rank": my_rank,
            "is_winner": is_winner,
            "participant_names": participant_names,
            "round_count": round_count,
            "winner": data.get("winner"),
            "result": _battle_result_for_uid(data, uid),
        }

    p1 = participants.get("p1", {})
    p2 = participants.get("p2", {})
    my_seat = _v1_user_seat(data, uid)
    if my_seat is None:
        return None

    opponent = p2.get("username", "?") if my_seat == "p1" else p1.get("username", "?")
    winner = data.get("winner")
    result = _battle_result_for_uid(data, uid)

    return {
        "battle_id": bid,
        "rule_version": rule_version,
        "start_time": data.get("start_time", ""),
        "end_time": data.get("end_time"),
        "mode": data.get("mode"),
        "mode_label": data.get("mode_label", ""),
        "opponent_type": data.get("opponent_type"),
        "ai_difficulty": data.get("ai_difficulty"),
        "ai_policy_type": data.get("ai_policy_type"),
        "ai_model_version": data.get("ai_model_version"),
        "p1_name": p1.get("username", "?"),
        "p2_name": p2.get("username", "?"),
        "opponent": opponent or "?",
        "result": result,
        "round_count": round_count,
        "winner": winner,
    }


def _ai_training_samples_from_battle(data: dict, uid: int) -> list[dict]:
    if not _is_ai_battle(data):
        return []

    battle_id = data.get("battle_id")
    ai_seat = data.get("ai_seat") or "p2"
    human_seat = data.get("human_seat") or ("p1" if ai_seat == "p2" else "p2")
    samples: list[dict] = []

    for round_data in data.get("rounds", []) or []:
        ai_move = round_data.get("ai_move") or round_data.get(f"{ai_seat}_move")
        human_move = round_data.get("human_move") or round_data.get(f"{human_seat}_move")
        if not ai_move or not human_move:
            continue

        samples.append({
            "schema": "clapclap-ai-human-battle-sample-v1",
            "battle_id": battle_id,
            "round_num": round_data.get("round_num"),
            "source_uid": uid,
            "rule_version": data.get("rule_version", "1.0"),
            "ai_seat": ai_seat,
            "human_seat": human_seat,
            "human_move": human_move,
            "ai_move": ai_move,
            "winner_after_round": round_data.get("winner_after_round"),
            "battle_winner": data.get("winner"),
            "ai_difficulty": round_data.get("ai_difficulty") or data.get("ai_difficulty"),
            "ai_policy_type": round_data.get("ai_policy_type") or data.get("ai_policy_type"),
            "ai_model_version": round_data.get("ai_model_version") or data.get("ai_model_version"),
            "round": round_data,
        })

    return samples


def _build_user_battle_stats(uid: int, battle_ids: list[str]) -> dict:
    stats = {
        "v1": {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "ongoing": 0,
        },
        "ai": {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "ongoing": 0,
        },
        "v2": {
            "total": 0,
            "completed": 0,
            "championships": 0,
            "ranked_count": 0,
            "average_rank": None,
            "by_player_count": {},
        },
    }

    rank_sum = 0
    player_count_rank_sums: dict[str, int] = {}

    for bid in battle_ids:
        data = read_battle(bid)
        if data is None:
            continue

        rule_version = str(data.get("rule_version", "1.0"))
        participants = data.get("participants", {}) or {}
        mode = data.get("mode")

        if rule_version.startswith("2."):
            player_id = _get_participant_player_id(participants, uid)
            if player_id is None:
                continue

            v2 = stats["v2"]
            v2["total"] += 1
            player_count = len(participants)
            key = str(player_count)
            bucket = v2["by_player_count"].setdefault(key, {
                "player_count": player_count,
                "total": 0,
                "completed": 0,
                "championships": 0,
                "ranked_count": 0,
                "average_rank": None,
            })
            bucket["total"] += 1

            if data.get("end_time") is not None:
                v2["completed"] += 1
                bucket["completed"] += 1

            if _v2_is_winner(data, player_id):
                v2["championships"] += 1
                bucket["championships"] += 1

            rank = _latest_v2_rank(data, player_id)
            if isinstance(rank, int):
                v2["ranked_count"] += 1
                rank_sum += rank
                bucket["ranked_count"] += 1
                player_count_rank_sums[key] = player_count_rank_sums.get(key, 0) + rank
            continue

        p1 = participants.get("p1", {})
        p2 = participants.get("p2", {})
        my_seat = None
        if p1.get("uid") == uid:
            my_seat = "p1"
        elif p2.get("uid") == uid:
            my_seat = "p2"
        if my_seat is None:
            continue

        bucket = stats["ai"] if mode == "ai" else stats["v1"]
        bucket["total"] += 1
        winner = data.get("winner")
        if data.get("end_time") is None and winner is None:
            bucket["ongoing"] += 1
        elif winner == 0:
            bucket["draws"] += 1
        elif (winner == 1 and my_seat == "p1") or (winner == 2 and my_seat == "p2"):
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1

    v2 = stats["v2"]
    if v2["ranked_count"]:
        v2["average_rank"] = round(rank_sum / v2["ranked_count"], 2)
    for key, bucket in v2["by_player_count"].items():
        if bucket["ranked_count"]:
            bucket["average_rank"] = round(player_count_rank_sums.get(key, 0) / bucket["ranked_count"], 2)

    return stats


@auth_bp.post("/v1/api/auth/register")
@auth_bp.post("/v2/api/auth/register")
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


@auth_bp.post("/v1/api/auth/login")
@auth_bp.post("/v2/api/auth/login")
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

    if _is_login_rate_limited(username):
        return jsonify({"ok": False, "error": "登录尝试过于频繁，请稍后再试。"}), 429

    result = users.login(username, password)
    if not result["ok"]:
        _record_failed_login(username)
        return jsonify(result), 401

    _clear_failed_logins(username)
    return jsonify(result), 200


@auth_bp.post("/v1/api/auth/guest")
@auth_bp.post("/v2/api/auth/guest")
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


@auth_bp.post("/v1/api/auth/logout")
@auth_bp.post("/v2/api/auth/logout")
@auth_bp.post("/api/auth/logout")
def api_logout():
    """登出。"""
    data = request.get_json(silent=True) or {}
    token = data.get("session_token") or request.headers.get("X-Session-Token", "")
    users.logout_token(token.strip())
    return jsonify({"ok": True, "message": "已登出。"}), 200


@auth_bp.get("/v1/api/auth/me")
@auth_bp.get("/v2/api/auth/me")
@auth_bp.get("/api/auth/me")
@require_auth
def api_me():
    """获取当前登录用户信息。"""
    return jsonify({
        "ok": True,
        "user": g.current_user,
    }), 200


@auth_bp.post("/v1/api/auth/update")
@auth_bp.post("/v2/api/auth/update")
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


@auth_bp.post("/v1/api/auth/delete")
@auth_bp.post("/v2/api/auth/delete")
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

@auth_bp.get("/v1/api/admin/users")
@auth_bp.get("/v2/api/admin/users")
@auth_bp.get("/api/admin/users")
@require_auth
def api_admin_users():
    """管理员查看所有用户列表。"""
    if not users.is_admin(g.current_user):
        return jsonify({"ok": False, "error": "权限不足。"}), 403

    all_users = users.get_all_users()
    return jsonify({"ok": True, "users": all_users}), 200


@auth_bp.post("/v1/api/admin/verify/<int:uid>")
@auth_bp.post("/v2/api/admin/verify/<int:uid>")
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


@auth_bp.post("/v1/api/admin/delete/<int:uid>")
@auth_bp.post("/v2/api/admin/delete/<int:uid>")
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

@auth_bp.get("/v1/api/user/<int:uid>")
@auth_bp.get("/v2/api/user/<int:uid>")
@auth_bp.get("/api/user/<int:uid>")
@require_auth
def api_get_user(uid: int):
    """获取用户公开信息。"""
    user = users.get_user_by_uid(uid)
    if user is None:
        return jsonify({"ok": False, "error": "用户不存在。"}), 404
    return jsonify({"ok": True, "user": user}), 200


@auth_bp.get("/v1/api/user/<int:uid>/battles")
@auth_bp.get("/v2/api/user/<int:uid>/battles")
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
    filters = _battle_filters_from_request()
    all_battle_ids = users.get_user_battle_ids(uid)
    filtered_battle_ids = _filtered_user_battle_ids(uid, filters)
    total = len(filtered_battle_ids)
    battle_ids = filtered_battle_ids[offset:offset + limit]
    stats = _build_user_battle_stats(uid, all_battle_ids)
    filtered_stats = _build_user_battle_stats(uid, filtered_battle_ids)
    battles: list[dict] = []

    for bid in battle_ids:
        data = read_battle(bid)
        if data is None:
            continue
        summary = _summarize_user_battle(uid, bid, data)
        if summary is not None:
            battles.append(summary)

    next_offset = offset + len(battle_ids)
    return jsonify({
        "ok": True,
        "battles": battles,
        "stats": stats,
        "filtered_stats": filtered_stats,
        "filters": filters,
        "total": total,
        "has_more": next_offset < total,
        "next_offset": next_offset,
    }), 200


@auth_bp.get("/v1/api/user/<int:uid>/battles/download")
@auth_bp.get("/v2/api/user/<int:uid>/battles/download")
@auth_bp.get("/api/user/<int:uid>/battles/download")
@require_auth
def api_user_battles_download(uid: int):
    """按当前筛选条件打包下载对局记录，并附带 AI 训练样本。"""
    if not users.user_exists(uid):
        return jsonify({"ok": False, "error": "用户不存在。"}), 404

    current_uid = g.current_user.get("uid") if hasattr(g, "current_user") else None
    if current_uid != uid and not users.is_admin(g.current_user):
        return jsonify({"ok": False, "error": "只能下载自己的对局记录。"}), 403

    filters = _battle_filters_from_request()
    battle_ids = _filtered_user_battle_ids(uid, filters)
    training_samples: list[dict] = []
    generated_at = datetime.now(timezone.utc).isoformat()

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for bid in battle_ids:
            data = read_battle(bid)
            if data is None:
                continue
            archive.writestr(
                f"battles/{bid}.json",
                json.dumps(data, ensure_ascii=False, indent=2),
            )
            training_samples.extend(_ai_training_samples_from_battle(data, uid))

        if training_samples:
            jsonl = "\n".join(
                json.dumps(sample, ensure_ascii=False, separators=(",", ":"))
                for sample in training_samples
            )
            archive.writestr("training/ai_battle_samples.jsonl", jsonl + "\n")

        manifest = {
            "schema": "clapclap-user-battle-export-v1",
            "generated_at": generated_at,
            "uid": uid,
            "filters": filters,
            "battle_count": len(battle_ids),
            "training_sample_count": len(training_samples),
            "contains": {
                "raw_battles": True,
                "ai_training_samples_jsonl": bool(training_samples),
            },
            "notes": [
                "raw_battles 可用于回放、审计和后续重新抽取训练特征。",
                "training/ai_battle_samples.jsonl 是从人机对局中抽出的轻量训练样本。",
            ],
        }
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    memory_file.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"clapclap_battles_uid{uid}_{timestamp}.zip",
    )


@auth_bp.get("/v1/api/battles/<battle_id>")
@auth_bp.get("/v2/api/battles/<battle_id>")
@auth_bp.get("/api/battles/<battle_id>")
@require_auth
def api_battle_detail(battle_id: str):
    """获取单个对局的完整记录。"""
    data = read_battle(battle_id)
    if data is None:
        return jsonify({"ok": False, "error": "对局不存在。"}), 404
    return jsonify({"ok": True, "battle": data}), 200
