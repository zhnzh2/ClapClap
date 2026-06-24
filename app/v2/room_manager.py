"""
ClapClap 2.0 多人房间管理器。

与 1.0 Room (app/room_manager.py) 完全独立。
管理 ROOMS_V2 内存字典，提供 CRUD 操作。
"""

from __future__ import annotations

import random
import string
import traceback
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.v2.room import RoomV2
from app.storage import save_room, load_room, delete_room, load_all_rooms


# ── 全局状态 ──
ROOMS_V2: dict[str, RoomV2] = {}
ROOMS_V2_LOCK = RLock()


def generate_room_id_v2(length: int = 6) -> str:
    """生成随机房间 ID（大写字母+数字）。"""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        room_id = "".join(random.choice(alphabet) for _ in range(length))
        if room_id not in ROOMS_V2:
            return room_id


def load_rooms_v2_from_storage() -> None:
    """从 SQLite 加载所有 v2 房间到内存。"""
    persisted = load_all_rooms()
    with ROOMS_V2_LOCK:
        ROOMS_V2.clear()

        for room_id, room_data in persisted.items():
            rule_version = room_data.get("rule_version", "1.0")
            if rule_version != "2.0":
                # 跳过 1.0 房间（由 load_all_rooms 统一返回）
                continue

            try:
                ROOMS_V2[room_id] = RoomV2.from_dict(room_data)
            except Exception as exc:
                print(f"[load_rooms_v2] 跳过无法兼容的旧房间 {room_id}: {exc}")
                traceback.print_exc()


def create_room_v2(
    host_name: str,
    *,
    max_players: int = 6,
    min_players: int = 2,
    start_condition: str = "host",
    allow_spectate: bool = True,
    public: bool = False,
    password: str | None = None,
) -> tuple[RoomV2, int, str]:
    """创建 2.0 多人房间。返回 (room, seat_index, player_token)。"""
    with ROOMS_V2_LOCK:
        room_id = generate_room_id_v2()
        room = RoomV2(
            room_id=room_id,
            max_players=max_players,
            min_players=min_players,
            start_condition=start_condition,
            allow_spectate=allow_spectate,
            public=public,
            password=password,
        )
        seat_index, player_token = room.add_player(host_name)
        ROOMS_V2[room_id] = room
        room.persist()
        return room, seat_index, player_token


def get_room_v2(room_id: str) -> RoomV2 | None:
    """获取 v2 房间（先从内存查，再按需从 SQLite 恢复）。"""
    with ROOMS_V2_LOCK:
        existing = ROOMS_V2.get(room_id)
        if existing is not None:
            return existing

    # 从 SQLite 恢复
    room_data = load_room(room_id)
    if room_data is None:
        return None

    try:
        restored_room = RoomV2.from_dict(room_data)
    except Exception as exc:
        print(f"[get_room_v2] 恢复房间 {room_id} 失败: {exc}")
        traceback.print_exc()
        return None

    with ROOMS_V2_LOCK:
        # 再次检查（可能在恢复期间被其他线程抢先创建）
        existing = ROOMS_V2.get(room_id)
        if existing is not None:
            return existing

        ROOMS_V2[room_id] = restored_room
        return restored_room


def join_room_v2(
    room_id: str,
    username: str,
    *,
    as_spectator: bool = False,
    seat_index: int | None = None,
) -> tuple[RoomV2, int, str]:
    """加入 2.0 房间。返回 (room, seat_index | -1, token)。"""
    room = get_room_v2(room_id)
    if room is None:
        raise ValueError("房间不存在。")

    with ROOMS_V2_LOCK:
        if as_spectator:
            token = room.add_spectator(username)
            room.persist()
            return room, -1, token

        # 加入参战席位
        si, player_token = room.add_player(username, requested_seat_index=seat_index)
        room.persist()
        return room, si, player_token


def leave_room_v2(room_id: str, player_token: str) -> tuple[str | None, str]:
    """退出 v2 房间。返回 (new_host_token | None, leave_type)。"""
    room = get_room_v2(room_id)
    if room is None:
        raise ValueError("房间不存在。")

    with ROOMS_V2_LOCK:
        new_host_token, leave_type = room.remove_player(player_token)
        room.persist()
        return new_host_token, leave_type


def mark_seen_v2(room_id: str, player_token: str) -> None:
    """标记 v2 玩家在线（心跳）。"""
    room = get_room_v2(room_id)
    if room is None:
        return

    room.mark_seen(player_token)
    room.persist()


def mark_disconnected_v2(room_id: str, player_token: str) -> None:
    """标记 v2 玩家断开连接。"""
    room = get_room_v2(room_id)
    if room is None:
        return

    room.mark_disconnected(player_token)
    room.persist()


def mark_reconnected_v2(room_id: str, player_token: str) -> None:
    """标记 v2 玩家重新连接。"""
    room = get_room_v2(room_id)
    if room is None:
        return

    room.mark_reconnected(player_token)
    room.persist()


def delete_room_v2(room_id: str) -> None:
    """删除 v2 房间。"""
    with ROOMS_V2_LOCK:
        ROOMS_V2.pop(room_id, None)
        delete_room(room_id)


def cleanup_expired_rooms_v2() -> list[str]:
    """清理过期的 v2 房间。"""
    deleted: list[str] = []

    with ROOMS_V2_LOCK:
        room_ids = list(ROOMS_V2.keys())

        for room_id in room_ids:
            room = ROOMS_V2.get(room_id)
            if room is None:
                continue

            if not room.is_expired():
                continue

            ROOMS_V2.pop(room_id, None)
            delete_room(room_id)
            deleted.append(room_id)

    return deleted


def persist_room_v2(room: RoomV2) -> None:
    """持久化 v2 房间到 SQLite。"""
    save_room(room.room_id, room.to_dict())
