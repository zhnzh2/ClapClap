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
import time
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
        data = json.loads(target.read_text(encoding="utf-8"))
        # 兼容旧记录：无 rule_version 视为 1.0
        if "rule_version" not in data:
            data["rule_version"] = "1.0"
        return data
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
    for attempt in range(5):
        try:
            os.replace(temporary, target)
            return
        except PermissionError:
            if attempt == 4:
                raise
            # Windows/OneDrive can briefly lock JSON files right after writes.
            time.sleep(0.05 * (attempt + 1))


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

def _format_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _mode_label(mode: str | None) -> str:
    if mode == "local":
        return "本地对战"
    if mode == "room":
        return "房间对战"
    if mode == "ai":
        return "人机对战"
    return ""


def _schema_version_for(rule_version: str) -> str:
    if str(rule_version).startswith("2."):
        return "2.0.0"
    return "1.0.0"


def create_battle(
    participants: dict,
    start_time: datetime | None = None,
    rule_version: str = "1.0",
    *,
    mode: str | None = None,
    seats: list[dict] | None = None,
    host: dict | None = None,
    room: dict | None = None,
    schema_version: str | None = None,
) -> str:
    """创建对局记录。participants = {seat: {username, uid}}。返回 battle_id。

    1.0 调用保持原样；2.0 可传入 mode/seats/host/room 形成完整表头。
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    with _lock:
        base_name = _timestamp_name(start_time)
        battle_id = _resolve_battle_name(base_name, participants)

        data = {
            "battle_id": battle_id,
            "schema_version": schema_version or _schema_version_for(rule_version),
            "rule_version": rule_version,
            "mode": mode,
            "mode_label": _mode_label(mode),
            "start_time": _format_timestamp(start_time),
            "end_time": None,
            "participants": {
                seat: {
                    "username": info["username"],
                    "uid": info["uid"],
                    "status": "active",
                    **({"seat_index": info["seat_index"]} if "seat_index" in info else {}),
                    **({"player_id": info["player_id"]} if "player_id" in info else {}),
                    **({"is_host": info["is_host"]} if "is_host" in info else {}),
                }
                for seat, info in participants.items()
            },
            "seats": seats or [],
            "host": host,
            "room": room or {},
            "spectators": [],
            "rounds": [],
            "chat": [],
        }

        _write_battle(battle_id, data)

        for info in participants.values():
            uid = info.get("uid")
            if isinstance(uid, int) and uid >= 0:
                _append_user_battle(uid, battle_id)

    return battle_id


def _snapshot_changes(pre: dict, post: dict) -> dict:
    """计算每名玩家回合前后资源变化，供回放直接展示。"""
    changes: dict[str, dict] = {}
    player_ids = set(pre.keys()) | set(post.keys())
    for pid in sorted(player_ids):
        before = pre.get(pid, {}) or {}
        after = post.get(pid, {}) or {}
        delta = {}
        for key in sorted(set(before.keys()) | set(after.keys())):
            old = before.get(key)
            new = after.get(key)
            if old != new:
                if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                    delta[key] = {"before": old, "after": new, "delta": new - old}
                else:
                    delta[key] = {"before": old, "after": new}
        if delta:
            changes[pid] = delta
    return changes


def _normalize_v2_round(round_data: dict) -> dict:
    """把 RoundLogV2.to_dict() 补成适合回放读取的完整事件化结构。"""
    normalized = dict(round_data)
    normalized["record_schema"] = "v2_round_full"

    declarations_by_layer = round_data.get("target_declarations_by_layer", {}) or {}
    conflicts_by_layer = round_data.get("conflicts_by_layer", {}) or {}
    decisions = round_data.get("decision_log", []) or []
    events = round_data.get("speed_layer_events", []) or []

    layer_numbers: set[int] = set()
    for source in (declarations_by_layer, conflicts_by_layer):
        for layer in source.keys():
            try:
                layer_numbers.add(int(layer))
            except (TypeError, ValueError):
                continue
    for item in events:
        try:
            layer_numbers.add(int(item.get("speed_layer", 0)))
        except (TypeError, ValueError):
            continue
    for item in decisions:
        try:
            layer_numbers.add(int(item.get("speed_layer", 0)))
        except (TypeError, ValueError):
            continue

    speed_layers = []
    for layer in sorted(layer_numbers):
        layer_key = str(layer)
        layer_events = [
            item for item in events
            if int(item.get("speed_layer", 0) or 0) == layer
        ]
        layer_decisions = [
            item for item in decisions
            if int(item.get("speed_layer", 0) or 0) == layer
        ]
        speed_layers.append({
            "layer": layer,
            "declarations": declarations_by_layer.get(layer_key, declarations_by_layer.get(layer, {})),
            "conflicts": conflicts_by_layer.get(layer_key, conflicts_by_layer.get(layer, [])),
            "decisions": layer_decisions,
            "events": layer_events,
            "had_conflict": bool(conflicts_by_layer.get(layer_key, conflicts_by_layer.get(layer, []))),
        })

    normalized["speed_layers"] = speed_layers
    normalized["changes"] = _snapshot_changes(
        round_data.get("pre_snapshots", {}) or {},
        round_data.get("post_snapshots", {}) or {},
    )
    normalized["result"] = {
        "deaths": round_data.get("deaths", []) or [],
        "rank_updates": round_data.get("rank_updates", {}) or {},
        "winner": round_data.get("winner"),
        "game_ended": bool(round_data.get("game_ended", False)),
    }
    return normalized


def record_round(battle_id: str, round_data: dict) -> None:
    """记录一回合的完整数据。round_data 来自 RoundLog.to_dict()，包含双方动作、
    资源快照、伤害、格挡、备注、回合胜者等完整信息。"""
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return
        if str(data.get("rule_version", "1.0")).startswith("2."):
            round_data = _normalize_v2_round(round_data)
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


def _derive_v2_final_result(data: dict, winner) -> dict:
    rankings = []
    latest_ranks = {}
    for round_data in reversed(data.get("rounds", [])):
        latest_ranks = round_data.get("rank_updates", {}) or round_data.get("result", {}).get("rank_updates", {})
        if latest_ranks:
            break

    participants = data.get("participants", {}) or {}
    for player_id, info in participants.items():
        rankings.append({
            "player_id": player_id,
            "seat_index": info.get("seat_index"),
            "username": info.get("username", player_id),
            "rank": latest_ranks.get(player_id),
            "is_winner": player_id == winner,
        })
    rankings.sort(key=lambda item: (
        item["rank"] is None,
        item["rank"] if item["rank"] is not None else 999,
        item["seat_index"] if item["seat_index"] is not None else 999,
    ))
    return {
        "winner": winner,
        "rankings": rankings,
    }


def end_battle(battle_id: str, winner: int | str | None) -> None:
    """标记对局结束。winner: 1=P1胜, 2=P2胜, 0=平局, None=未知。"""
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return
        now = datetime.now(timezone.utc)
        data["end_time"] = _format_timestamp(now)
        data["winner"] = winner
        if str(data.get("rule_version", "1.0")).startswith("2."):
            data["final_result"] = _derive_v2_final_result(data, winner)
        _write_battle(battle_id, data)


def set_battle_metadata(battle_id: str, metadata: dict) -> None:
    """向已有对局记录写入额外元数据（如 AI 对局信息）。

    不会覆盖已有字段的同名值；只写入尚不存在的键。
    """
    with _lock:
        data = read_battle(battle_id)
        if data is None:
            return
        changed = False
        for key, value in metadata.items():
            if key not in data:
                data[key] = value
                changed = True
        if changed:
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


# ── 清理过期对局 ────────────────────────────────────────────

def cleanup_stale_battles(max_age_minutes: int = 30) -> int:
    """删除超过 max_age_minutes 分钟前创建、且仍处于"进行中"的对局。

    在对局记录页面打开时调用，清理被遗弃的未完成对局。
    返回删除的对局数量。
    """
    _ensure_dirs()
    now = datetime.now(timezone.utc)
    deleted_count = 0
    stale_ids: list[str] = []

    for path in sorted(BATTLES_DIR.glob("*.json")):
        if path.parent != BATTLES_DIR:
            continue

        battle_id = path.stem
        # 从文件名解析创建时间
        try:
            created = datetime.strptime(battle_id, "%Y%m%d%H%M%S%f")
            created = created.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        age_minutes = (now - created).total_seconds() / 60.0
        if age_minutes <= max_age_minutes:
            continue

        # 快速检查是否"进行中"（end_time 为 null）
        try:
            raw = path.read_text(encoding="utf-8")
            # 不需要完整解析 JSON，只检查 end_time 字段
            if '"end_time": null' not in raw and '"end_time":null' not in raw:
                continue
        except Exception:
            continue

        # 确认后完整读取并删除
        data = read_battle(battle_id)
        if data is None:
            continue
        if data.get("end_time") is not None:
            continue

        if delete_battle(battle_id):
            stale_ids.append(battle_id)
            deleted_count += 1

    if stale_ids:
        print(f"[battle] 清理了 {deleted_count} 个过期进行中对局（>{max_age_minutes}分钟）：{stale_ids}")

    return deleted_count


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
                _write_battle(battle_id, data)
                # 移入 rub
                rub_path = _rub_path(battle_id)
                shutil.move(str(path), str(rub_path))
                moved_to_rub.append(battle_id)
            else:
                _write_battle(battle_id, data)

    if moved_to_rub:
        print(f"[battle] 以下对局所有参与者均已注销，移入 rub/: {moved_to_rub}")
