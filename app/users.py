"""
用户存储模块。

目录结构：
  DATA_DIR/users/
  ├── users.csv          # UID,用户名,密码,创建时间,已验证,权限
  ├── User_0/            # admin 账号（zhnzh）
  ├── User_1/
  │   ├── username       # 用户名
  │   ├── password       # 密码（SHA-256 哈希）
  │   ├── intro          # 介绍信
  │   ├── session        # 当前登录 session token
  │   ├── created_at     # 创建时间（ISO 8601，服务器时间）
  │   ├── verified       # "1"=已验证, "0"=未验证
  │   └── role           # "admin" 或 "user"
  ...

CSV 用于快速登录校验和 UID 分配。
User_X/ 文件夹是每个用户数据的完整存储。

密码哈希：PBKDF2-SHA256；旧版 SHA-256 哈希会在用户下次登录成功时自动升级。
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import os
import secrets
import shutil
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.storage import DATA_DIR

USERS_DIR = DATA_DIR / "users"
CSV_PATH = USERS_DIR / "users.csv"

# 未验证账号最长存活天数
UNVERIFIED_MAX_DAYS = 30
SESSION_MAX_AGE_DAYS = int(os.environ.get("CLAPCLAP_SESSION_MAX_AGE_DAYS", "7"))
PASSWORD_HASH_ITERATIONS = int(os.environ.get("CLAPCLAP_PASSWORD_HASH_ITERATIONS", "200000"))

_csv_lock = threading.RLock()
_session_lock = threading.RLock()
_session_to_uid: dict[str, int] = {}
_uid_to_session: dict[int, str] = {}
_session_index_source: str | None = None

# ── CSV 列定义 ──────────────────────────────────────────────
CSV_FIELDS = ["UID", "用户名", "密码", "创建时间", "已验证", "权限"]


# ── 工具函数 ──────────────────────────────────────────────────

def _server_now() -> str:
    """返回服务器当前 UTC 时间（ISO 8601）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _server_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_dirs() -> None:
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        CSV_PATH.write_text(",".join(CSV_FIELDS) + "\n", encoding="utf-8")


def _user_dir(uid: int) -> Path:
    return USERS_DIR / f"User_{uid}"


def _read_file(filepath: Path) -> str:
    if filepath.exists():
        return filepath.read_text(encoding="utf-8").strip()
    return ""


def _hash_password(password: str, uid: int) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        f"{salt}:{uid}".encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${derived}"


def _legacy_hash_password(password: str, uid: int) -> str:
    return hashlib.sha256((password + "clapclap" + str(uid)).encode("utf-8")).hexdigest()


def _verify_password_hash(password: str, uid: int, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _algo, iterations_raw, salt, expected = stored_hash.split("$", 3)
            iterations = int(iterations_raw)
        except (ValueError, TypeError):
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            f"{salt}:{uid}".encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(expected, derived)
    return hmac.compare_digest(stored_hash, _legacy_hash_password(password, uid))


def _password_hash_needs_upgrade(stored_hash: str) -> bool:
    return not stored_hash.startswith("pbkdf2_sha256$")


def _ensure_session_index() -> None:
    """Load persisted sessions once, rebuilding when the storage root changes."""
    global _session_index_source
    source = str(USERS_DIR.resolve())
    with _session_lock:
        if _session_index_source == source:
            return
        _session_to_uid.clear()
        _uid_to_session.clear()
        if USERS_DIR.exists():
            for user_dir in USERS_DIR.glob("User_*"):
                try:
                    uid = int(user_dir.name.removeprefix("User_"))
                except ValueError:
                    continue
                token = _read_file(user_dir / "session")
                if token:
                    _session_to_uid[token] = uid
                    _uid_to_session[uid] = token
        _session_index_source = source


def _set_session(uid: int, token: str) -> None:
    _ensure_session_index()
    with _session_lock:
        previous = _uid_to_session.pop(uid, "")
        if previous:
            _session_to_uid.pop(previous, None)
        if token:
            _uid_to_session[uid] = token
            _session_to_uid[token] = uid
        (_user_dir(uid) / "session").write_text(token, encoding="utf-8")
        (_user_dir(uid) / "session_created_at").write_text(_server_now(), encoding="utf-8")


def _migrate_csv_row(row: dict) -> dict:
    """兼容旧格式 CSV 行（只有 3 列），补全为 6 列。"""
    return {
        "UID": row.get("UID", ""),
        "用户名": row.get("用户名", ""),
        "密码": row.get("密码", ""),
        "创建时间": row.get("创建时间", ""),
        "已验证": row.get("已验证", "0"),
        "权限": row.get("权限", "user"),
    }


def _read_csv() -> list[dict]:
    """读取 users.csv，返回完整字段列表。"""
    _ensure_dirs()
    with _csv_lock:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [_migrate_csv_row(row) for row in reader]


def _write_csv(rows: list[dict]) -> None:
    with _csv_lock:
        fd, tmp_name = tempfile.mkstemp(
            prefix="users_",
            suffix=".csv.tmp",
            dir=str(USERS_DIR),
            text=True,
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for row in rows:
                    writer.writerow({
                        k: row.get(k, "") for k in CSV_FIELDS
                    })
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, CSV_PATH)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


def _append_csv_row(row: dict) -> None:
    with _csv_lock:
        rows = _read_csv()
        rows.append({k: row.get(k, "") for k in CSV_FIELDS})
        _write_csv(rows)


def _write_user_folder(uid: int, username: str, password_hash: str,
                       intro: str, created_at: str, verified: str, role: str) -> None:
    user_dir = _user_dir(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    try:
        (user_dir / "username").write_text(username, encoding="utf-8")
        (user_dir / "password").write_text(password_hash, encoding="utf-8")
        (user_dir / "intro").write_text(intro, encoding="utf-8")
        (user_dir / "session").write_text("", encoding="utf-8")
        (user_dir / "session_created_at").write_text("", encoding="utf-8")
        (user_dir / "created_at").write_text(created_at, encoding="utf-8")
        (user_dir / "verified").write_text(verified, encoding="utf-8")
        (user_dir / "role").write_text(role, encoding="utf-8")
    except Exception:
        shutil.rmtree(user_dir, ignore_errors=True)
        raise


def _update_csv_row(uid: int, **kwargs) -> bool:
    rows = _read_csv()
    found = False
    for row in rows:
        if row["UID"] == str(uid):
            found = True
            for k, v in kwargs.items():
                if k in CSV_FIELDS:
                    row[k] = str(v) if v is not None else ""
            break
    if found:
        _write_csv(rows)
    return found


def _delete_csv_row(uid: int) -> bool:
    rows = _read_csv()
    new_rows = [r for r in rows if r["UID"] != str(uid)]
    if len(new_rows) == len(rows):
        return False
    _write_csv(new_rows)
    return True


# ── UID 分配 ──────────────────────────────────────────────────

def _assign_uid() -> int:
    """分配单调递增 UID，避免删除用户后新用户复用旧 UID。"""
    rows = _read_csv()
    max_uid = 0
    for row in rows:
        try:
            max_uid = max(max_uid, int(row["UID"]))
        except (ValueError, KeyError):
            pass
    return max_uid + 1


def _assign_visitor_uid() -> int:
    """为访客分配未使用五位数 UID（10000-99999），优先最小。"""
    rows = _read_csv()
    used: set[int] = set()
    for row in rows:
        try:
            used.add(int(row["UID"]))
        except (ValueError, KeyError):
            pass
    uid = max(10000, max((value for value in used if value >= 10000), default=9999) + 1)
    if uid < 100000:
        return uid
    return _assign_uid()


# ── 用户 CRUD ─────────────────────────────────────────────────

def register(username: str, password: str, intro: str = "",
             verified: str = "0", role: str = "user", uid: int | None = None) -> dict:
    """注册新用户。可指定 uid，不指定则自动分配。成功返回 {"ok": True, "user": {...}}。"""
    username = username.strip()
    intro = intro.strip()

    if not username:
        return {"ok": False, "error": "用户名不能为空。"}
    if len(username) > 32:
        return {"ok": False, "error": "用户名不能超过 32 个字符。"}
    if not password:
        return {"ok": False, "error": "密码不能为空。"}
    if len(password) < 4:
        return {"ok": False, "error": "密码至少需要 4 个字符。"}
    if len(password) > 128:
        return {"ok": False, "error": "密码不能超过 128 个字符。"}

    # 检查用户名是否已存在
    with _csv_lock:
        rows = _read_csv()
        for row in rows:
            if row["用户名"] == username:
                return {"ok": False, "error": "该用户名已被注册。"}

        if uid is None:
            uid = _assign_uid()
        else:
            # 检查指定 uid 是否已被占用
            for row in rows:
                if row["UID"] == str(uid):
                    return {"ok": False, "error": f"UID {uid} 已被占用。"}
        pw_hash = _hash_password(password, uid)
        created_at = _server_now()

        _write_user_folder(uid, username, pw_hash, intro, created_at, verified, role)
        try:
            _append_csv_row({
                "UID": str(uid),
                "用户名": username,
                "密码": pw_hash,
                "创建时间": created_at,
                "已验证": verified,
                "权限": role,
            })
        except Exception:
            shutil.rmtree(_user_dir(uid), ignore_errors=True)
            raise

    return {
        "ok": True,
        "user": _build_user_dict(uid, username, intro, created_at, verified, role),
    }


def guest_register() -> dict:
    """访客自动注册。UID 与用户名中的五位数一致。"""
    uid = _assign_visitor_uid()
    username = f"visitor_{uid:05d}"
    default_password = "ClapClap"

    return register(username, default_password, intro="", verified="0", role="user", uid=uid)


def login(username: str, password: str) -> dict:
    """登录。成功返回 {"ok": True, "user": {...}, "session_token": "..."}。"""
    username = username.strip()

    if not username or not password:
        return {"ok": False, "error": "用户名和密码不能为空。"}

    rows = _read_csv()
    uid = None
    stored_hash = None
    for row in rows:
        if row["用户名"] == username:
            uid = int(row["UID"])
            stored_hash = row["密码"]
            break

    if uid is None:
        return {"ok": False, "error": "用户名或密码错误。"}

    if not _verify_password_hash(password, uid, stored_hash or ""):
        return {"ok": False, "error": "用户名或密码错误。"}

    if stored_hash and _password_hash_needs_upgrade(stored_hash):
        new_hash = _hash_password(password, uid)
        (_user_dir(uid) / "password").write_text(new_hash, encoding="utf-8")
        _update_csv_row(uid, **{"密码": new_hash})

    session_token = secrets.token_hex(32)

    user_dir = _user_dir(uid)
    _set_session(uid, session_token)

    intro = _read_file(user_dir / "intro")
    created_at = _read_file(user_dir / "created_at")
    verified = _read_file(user_dir / "verified")
    role = _read_file(user_dir / "role")

    return {
        "ok": True,
        "user": _build_user_dict(uid, username, intro, created_at, verified, role),
        "session_token": session_token,
    }


def get_user_by_session_token(token: str) -> dict | None:
    """根据 session token 获取用户信息。返回 None 表示未登录或 token 无效。"""
    token = token.strip()
    if not token:
        return None

    _ensure_session_index()
    with _session_lock:
        uid = _session_to_uid.get(token)
    if uid is None:
        return None
    user_dir = _user_dir(uid)
    if not user_dir.is_dir():
        with _session_lock:
            _session_to_uid.pop(token, None)
            _uid_to_session.pop(uid, None)
        return None
    created_raw = _read_file(user_dir / "session_created_at")
    if created_raw:
        try:
            created_at = datetime.strptime(created_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if _server_now_dt() - created_at > timedelta(days=SESSION_MAX_AGE_DAYS):
                logout_token(token)
                return None
        except ValueError:
            logout_token(token)
            return None
    else:
        # 兼容旧会话：首次读取时补写创建时间，之后按新规则过期。
        (user_dir / "session_created_at").write_text(_server_now(), encoding="utf-8")
    return get_user_by_uid(uid)


def verify_password(uid: int, password: str) -> bool:
    """Validate a user's current password without exposing its stored hash."""
    if not password:
        return False
    stored_hash = _read_file(_user_dir(uid) / "password")
    return _verify_password_hash(password, uid, stored_hash)


def update_user(uid: int, username: str | None = None, password: str | None = None,
                intro: str | None = None) -> dict:
    """更新用户信息。至少传入一个字段。"""
    user_dir = _user_dir(uid)
    if not user_dir.is_dir():
        return {"ok": False, "error": "用户不存在。"}

    current_username = _read_file(user_dir / "username")

    if username is not None:
        username = username.strip()
        if not username:
            return {"ok": False, "error": "用户名不能为空。"}
        if len(username) > 32:
            return {"ok": False, "error": "用户名不能超过 32 个字符。"}
        rows = _read_csv()
        for row in rows:
            if int(row["UID"]) != uid and row["用户名"] == username:
                return {"ok": False, "error": "该用户名已被使用。"}

    if password is not None:
        if len(password) < 4:
            return {"ok": False, "error": "密码至少需要 4 个字符。"}
        if len(password) > 128:
            return {"ok": False, "error": "密码不能超过 128 个字符。"}

    if username is not None:
        (user_dir / "username").write_text(username, encoding="utf-8")
        _update_csv_row(uid, **{"用户名": username})

    if password is not None:
        pw_hash = _hash_password(password, uid)
        (user_dir / "password").write_text(pw_hash, encoding="utf-8")
        _update_csv_row(uid, **{"密码": pw_hash})

    if intro is not None:
        intro = intro.strip()
        (user_dir / "intro").write_text(intro, encoding="utf-8")

    new_username = _read_file(user_dir / "username")
    if username is not None:
        new_username = username
    new_intro = _read_file(user_dir / "intro") if intro is None else intro.strip()

    return {
        "ok": True,
        "user": _build_user_dict(
            uid, new_username, new_intro,
            _read_file(user_dir / "created_at"),
            _read_file(user_dir / "verified"),
            _read_file(user_dir / "role"),
        ),
    }


def delete_user(uid: int) -> bool:
    """永久删除用户及其所有数据（含关联房间和匹配状态）。UID 不再回收复用。"""
    if uid == 0:
        return False  # admin 账号不可删除

    user_dir = _user_dir(uid)
    if not user_dir.is_dir():
        return _delete_csv_row(uid)  # 清理 CSV 残留

    # 读取用户名，用于清理关联的游戏数据
    username = _read_file(user_dir / "username")

    _ensure_session_index()
    with _session_lock:
        token = _uid_to_session.pop(uid, "")
        if token:
            _session_to_uid.pop(token, None)

    # 删除用户文件夹
    shutil.rmtree(user_dir)

    # 删除 CSV 行
    deleted = _delete_csv_row(uid)

    # 清理该用户创建/加入的房间和匹配状态
    if username:
        _cleanup_user_game_data(username)
        # 在对局记录中标记该用户已注销
        try:
            from app.battle_recorder import mark_user_deleted_in_battles
            mark_user_deleted_in_battles(username, uid)
        except Exception:
            pass

    return deleted


def _cleanup_user_game_data(username: str) -> None:
    """清理指定用户名的所有房间和匹配数据。"""
    import app.v1.matchmaking as mm_v1
    import app.v2.matchmaking as mm_v2
    from app.v1.room_manager import ROOMS, delete_room_by_id
    from app.v2.room_manager import ROOMS_V2, delete_room_v2

    # 清理相关房间
    rooms_to_delete: list[str] = []
    for room_id, room in ROOMS.items():
        if room.p1_name == username or room.p2_name == username:
            rooms_to_delete.append(room_id)

    for room_id in rooms_to_delete:
        try:
            mm_v1.clear_match_state_by_room(room_id)
            delete_room_by_id(room_id)
        except Exception:
            pass

    rooms_v2_to_delete: list[str] = []
    for room_id, room in ROOMS_V2.items():
        player_names = [getattr(seat, "username", "") for seat in getattr(room, "seats", [])]
        spectator_names = [getattr(spectator, "username", "") for spectator in getattr(room, "spectators", [])]
        if username in player_names or username in spectator_names:
            rooms_v2_to_delete.append(room_id)

    for room_id in rooms_v2_to_delete:
        try:
            delete_room_v2(room_id)
        except Exception:
            pass

    # 清理匹配队列中的等待者
    match_v1_changed = False
    if mm_v1.MATCH_WAITING is not None and mm_v1.MATCH_WAITING.player_name == username:
        mm_v1.MATCH_WAITING = None
        match_v1_changed = True

    # 清理 PLAYER_MATCH_STATE 中属于该用户的条目
    for token, state in list(mm_v1.PLAYER_MATCH_STATE.items()):
        if state.get("player_name") == username:
            mm_v1.PLAYER_MATCH_STATE.pop(token, None)
            match_v1_changed = True

    if match_v1_changed:
        try:
            mm_v1.persist_match_state()
        except Exception:
            pass

    match_v2_changed = False
    with mm_v2.MATCH_LOCK_V2:
        before_count = len(mm_v2.MATCH_QUEUE_V2)
        mm_v2.MATCH_QUEUE_V2 = [
            waiting for waiting in mm_v2.MATCH_QUEUE_V2
            if waiting.player_name != username
        ]
        if len(mm_v2.MATCH_QUEUE_V2) != before_count:
            match_v2_changed = True

        for token, state in list(mm_v2.PLAYER_MATCH_STATE_V2.items()):
            if state.get("player_name") == username:
                mm_v2.PLAYER_MATCH_STATE_V2.pop(token, None)
                match_v2_changed = True

        if match_v2_changed:
            try:
                mm_v2._persist_match_state_v2()
            except Exception:
                pass

    if rooms_to_delete:
        print(f"[users] 删除用户 {username} 时清理了 {len(rooms_to_delete)} 个关联 v1 房间: {rooms_to_delete}")

    if rooms_v2_to_delete:
        try:
            room_list = rooms_v2_to_delete
            print(f"[users] 删除用户 {username} 时清理了 {len(room_list)} 个关联 v2 房间: {room_list}")
        except Exception:
            pass


def logout_token(token: str) -> bool:
    """登出，清除 session token。"""
    token = token.strip()
    if not token:
        return False
    _ensure_session_index()
    with _session_lock:
        uid = _session_to_uid.pop(token, None)
        if uid is None:
            return False
        _uid_to_session.pop(uid, None)
        session_file = _user_dir(uid) / "session"
        if session_file.exists():
            session_file.write_text("", encoding="utf-8")
        return True


# ── 验证 ──────────────────────────────────────────────────────

def verify_user(uid: int) -> bool:
    """将用户标记为已验证。返回是否成功。"""
    user_dir = _user_dir(uid)
    if not user_dir.is_dir():
        return False
    (user_dir / "verified").write_text("1", encoding="utf-8")
    _update_csv_row(uid, **{"已验证": "1"})
    return True


# ── 管理员 ────────────────────────────────────────────────────

def ensure_admin_account() -> None:
    """确保 admin 账号（zhnzh, UID=0）存在。不存在则创建。"""
    rows = _read_csv()
    for row in rows:
        if row["UID"] == "0":
            return  # admin 已存在

    username = "zhnzh"
    password = os.environ.get("CLAPCLAP_ADMIN_PASSWORD", "").strip()
    if not password:
        password = secrets.token_urlsafe(18)
        print("[users] 已创建初始管理员 zhnzh。请设置 CLAPCLAP_ADMIN_PASSWORD 后重建生产管理员密码；本次临时密码仅输出一次:", password)
    uid = 0
    pw_hash = _hash_password(password, uid)
    created_at = _server_now()

    _write_user_folder(uid, username, pw_hash, "", created_at, "1", "admin")
    _append_csv_row({
        "UID": "0",
        "用户名": username,
        "密码": pw_hash,
        "创建时间": created_at,
        "已验证": "1",
        "权限": "admin",
    })


def get_all_users() -> list[dict]:
    """获取所有用户的完整列表（管理员用）。"""
    rows = _read_csv()
    result = []
    for row in rows:
        try:
            uid = int(row["UID"])
        except (ValueError, KeyError):
            continue

        user_dir = _user_dir(uid)
        result.append({
            "uid": uid,
            "username": row.get("用户名", ""),
            "created_at": row.get("创建时间", ""),
            "verified": row.get("已验证", "0"),
            "role": row.get("权限", "user"),
            "intro": _read_file(user_dir / "intro"),
        })
    # 按 UID 排序
    result.sort(key=lambda u: u["uid"])
    return result


def is_admin(user: dict) -> bool:
    """检查用户是否为管理员。"""
    return user.get("role") == "admin"


# ── 过期清理 ──────────────────────────────────────────────────

def cleanup_unverified_accounts() -> list[int]:
    """删除所有创建超过 30 天且未验证的账号。
    返回被删除的 UID 列表。
    """
    rows = _read_csv()
    now = _server_now_dt()
    deleted: list[int] = []

    for row in rows:
        if row.get("已验证") == "1":
            continue
        if row.get("UID") == "0":
            continue  # 不删 admin

        created_str = row.get("创建时间", "")
        if not created_str:
            continue

        try:
            created_dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if now - created_dt > timedelta(days=UNVERIFIED_MAX_DAYS):
            try:
                uid = int(row["UID"])
                delete_user(uid)
                deleted.append(uid)
            except (ValueError, KeyError):
                continue

    if deleted:
        print(f"[users] 清理未验证账号，已删除: {deleted}")

    return deleted


# ── 辅助 ──────────────────────────────────────────────────────

def _build_user_dict(uid: int, username: str, intro: str,
                     created_at: str, verified: str, role: str) -> dict:
    return {
        "uid": uid,
        "username": username,
        "intro": intro,
        "created_at": created_at,
        "verified": verified,
        "role": role,
    }


def user_exists(uid: int) -> bool:
    return _user_dir(uid).is_dir()


def lookup_uid(username: str) -> int:
    """根据用户名查找 UID，找不到返回 -1。"""
    rows = _read_csv()
    for row in rows:
        if row["用户名"] == username:
            try:
                return int(row["UID"])
            except (ValueError, KeyError):
                pass
    return -1


def get_user_by_uid(uid: int) -> dict | None:
    """根据 UID 获取用户公开信息。"""
    if not user_exists(uid):
        return None
    rows = _read_csv()
    for row in rows:
        try:
            if int(row["UID"]) == uid:
                user_dir = _user_dir(uid)
                return _build_user_dict(
                    uid=uid,
                    username=row.get("用户名", ""),
                    intro=_read_file(user_dir / "intro"),
                    created_at=row.get("创建时间", ""),
                    verified=row.get("已验证", "0"),
                    role=row.get("权限", "user"),
                )
        except (ValueError, KeyError):
            continue
    return None


def get_user_battle_ids(uid: int) -> list[str]:
    """获取用户参与的所有对局 ID 列表（按时间倒序）。"""
    user_dir = _user_dir(uid)
    battles_file = user_dir / "battles"
    if not battles_file.is_file():
        return []
    text = _read_file(battles_file).strip()
    if not text:
        return []
    # 每行一个 battle_id，倒序（最新的在前）
    ids = [line.strip() for line in text.splitlines() if line.strip()]
    ids.reverse()
    return ids
