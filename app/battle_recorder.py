"""
对战记录模块。

目录结构：
  DATA_DIR/battles/
  ├── 202606161954013847.json    # 对局记录
  ├── 202606161954013848.json
  └── rub/                        # 全员注销的对局
      └── ...

每局 JSON 结构：
  {
    "battle_id": "202606161954013847",
    "start_time": "2026-06-16T19:54:01.384Z",
    "end_time": null,
    "participants": {
      "p1": {"username": "alice", "uid": 1, "status": "active"},
      "p2": {"username": "bob",   "uid": 2, "status": "active"}
    },
    "spectators": [],
    "rounds": [
      {"round_num": 1, "p1_move": "gun", "p2_move": "defend"}
    ],
    "chat": [
      {"timestamp": "2026-06-16T19:54:05.123Z", "sender": "alice", "message": "hi"}
    ]
  }

命名规则：YYYYMMDDHHmmssSSS（精确到毫秒）。
冲突解决：同毫秒内，参与者最低 UID 的对局优先获得该名称，其余顺延。
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.storage import DATA_DIR

BATTLES_DIR = DATA_DIR / "battles"
RUB_DIR = BATTLES_DIR / "rub"

_lock = threading.RLock()


def _ensure_dirs() -> None:
    BATTLES_DIR.mkdir(parents=True, exist_ok=True)
    RUB_DIR.mkdir(parents=True, exist_ok=True)


def _battle_path(battle_id: str) -> Path:
    return BATTLES_DIR / f"{battle_id}.json"


def _rub_path(battle_id: str) -> Path:
    return RUB_DIR / f"{battle_id}.json"


def read_battle(battle_id: str) -> dict | None:
    if len(battle_id) != 17 or not battle_id.isdigit():
        return None
    path = _battle_path(battle_id)
    rub = _rub_path(battle_id)
    target = path if path.exists() else (rub if rub.exists() else None)
    if target is None:
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_battle(battle_id: str, data: dict) -> None:
    _ensure_dirs()
    target = _battle_path(battle_id)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, target)


# ── 命名 ──────────────────────────────────────────────────────

def _timestamp_name(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S") + f"{dt.microsecond // 1000:03d}"


def _lowest_uid(participants: dict) -> int:
    """返回参与者中最低的 UID。"""
    min_uid = None
    for seat_info in participants.values():
        uid = seat_info.get("uid")
        if uid is not None and (min_uid is None or uid < min_uid):
            min_uid = uid
    return min_uid if min_uid is not None else 999999


def _resolve_battle_name(base_name: str, participants: dict) -> str:
    """解决命名冲突：最低 UID 获得原始名称，其余顺延。"""
    with _lock:
        candidate = base_name
        while True:
            existing = read_battle(candidate)
            if existing is None:
                return candidate

            # 比较最低 UID
            new_lowest = _lowest_uid(participants)
            existing_lowest = _lowest_uid(existing.get("participants", {}))

            if new_lowest < existing_lowest:
                # 新对局优先级更高：让旧对局改名，新对局用此名
                old_data = existing
                old_id = candidate
                new_id = _resolve_battle_name(_increment_name(candidate), existing.get("participants", {}))
                old_data["battle_id"] = new_id
                _write_battle(new_id, old_data)
                _battle_path(old_id).unlink(missing_ok=True)
                # 更新所有参与用户的 battles 文件
                _rename_in_user_battles(old_id, new_id)
                return candidate
            else:
                # 旧对局优先级更高：新对局顺延
                candidate = _increment_name(candidate)


def _increment_name(name: str) -> str:
    """给时间戳名称加 1 毫秒。"""
    base = int(name)
    return str(base + 1).zfill(17)


# ── 创建 / 更新 ──────────────────────────────────────────────

def create_battle(participants: dict, start_time: datetime | None = None) -> str:
    """创建对局记录。participants = {seat: {username, uid}}。返回 battle_id。"""
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    with _lock:
        base_name = _timestamp_name(start_time)
        battle_id = _resolve_battle_name(base_name, participants)

        data = {
            "battle_id": battle_id,
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{start_time.microsecond // 1000:03d}Z",
            "end_time": None,
            "participants": {
                seat: {"username": info["username"], "uid": info["uid"], "status": "active"}
                for seat, info in participants.items()
            },
            "spectators": [],
            "rounds": [],
            "chat": [],
        }

        _write_battle(battle_id, data)

        for info in participants.values():
            _append_user_battle(info["uid"], battle_id)

    return battle_id


def record_round(battle_id: str, round_data: dict) -> None:
    """记录一回合的完整数据。round_data 来自 RoundLog.to_dict()，包含双方动作、
    资源快照、伤害、格挡、备注、回合胜者等完整信息。"""
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return
        data.setdefault("rounds", []).append(round_data)
        _write_battle(battle_id, data)


def record_chat(battle_id: str, timestamp: str, sender: str, message: str) -> None:
    """追加一条聊天记录。"""
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return
        data.setdefault("chat", []).append({
            "timestamp": timestamp,
            "sender": sender,
            "message": message,
        })
        _write_battle(battle_id, data)


def end_battle(battle_id: str, winner: int | None) -> None:
    """标记对局结束。winner: 1=P1胜, 2=P2胜, 0=平局, None=未知。"""
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return
        now = datetime.now(timezone.utc)
        data["end_time"] = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        data["winner"] = winner
        _write_battle(battle_id, data)


def add_spectator(battle_id: str, spectator_name: str) -> None:
    """添加观战者。"""
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return
        spectators = data.setdefault("spectators", [])
        if spectator_name not in spectators:
            spectators.append(spectator_name)
            _write_battle(battle_id, data)


# ── 用户 battles 索引 ─────────────────────────────────────────

def _user_battles_file(uid: int) -> Path:
    from app.users import USERS_DIR
    return USERS_DIR / f"User_{uid}" / "battles"


def _append_user_battle(uid: int, battle_id: str) -> None:
    """在用户文件夹中追加对局记录。"""
    path = _user_battles_file(uid)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        existing = set(path.read_text(encoding="utf-8").strip().splitlines())
    if battle_id not in existing:
        with open(path, "a", encoding="utf-8") as f:
            f.write(battle_id + "\n")


def _rename_in_user_battles(old_id: str, new_id: str) -> None:
    """当对局改名时更新用户 battles 文件。"""
    data = read_battle(new_id)
    if data is None:
        return
    for info in data.get("participants", {}).values():
        uid = info.get("uid")
        if uid is None:
            continue
        path = _user_battles_file(uid)
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        new_lines = [new_id if line.strip() == old_id else line for line in lines]
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def delete_battle(battle_id: str) -> bool:
    """Delete a battle and remove it from participant indexes."""
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return False
        for info in data.get("participants", {}).values():
            uid = info.get("uid")
            if uid is None:
                continue
            path = _user_battles_file(uid)
            if not path.exists():
                continue
            lines = [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and line.strip() != battle_id
            ]
            path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
        _battle_path(battle_id).unlink(missing_ok=True)
        _rub_path(battle_id).unlink(missing_ok=True)
        return True


# ── 用户注销处理 ─────────────────────────────────────────────

def mark_user_deleted_in_battles(username: str, uid: int) -> None:
    """将指定用户在所有对局中标记为 deleted。
    如果某对局所有参与者均已注销，将其移入 rub/。
    """
    _ensure_dirs()
    all_battles = sorted(BATTLES_DIR.glob("*.json"))
    moved_to_rub: list[str] = []

    for path in all_battles:
        if path.parent != BATTLES_DIR:
            continue  # 跳过 rub 子目录

        battle_id = path.stem
        data = read_battle(battle_id)
        if data is None:
            continue

        changed = False

        # 标记参与者
        for seat_info in data.get("participants", {}).values():
            if seat_info.get("username") == username and seat_info.get("status") != "deleted":
                seat_info["status"] = "deleted"
                changed = True

        if changed:
            # 检查是否所有参与者都已注销
            all_deleted = all(
                info.get("status") == "deleted"
                for info in data.get("participants", {}).values()
            )
            if all_deleted:
                # 移入 rub
                rub_path = _rub_path(battle_id)
                shutil.move(str(path), str(rub_path))
                moved_to_rub.append(battle_id)
            else:
                _write_battle(battle_id, data)

    if moved_to_rub:
        print(f"[battle] 以下对局所有参与者均已注销，移入 rub/: {moved_to_rub}")
