"""
ClapClap 2.0 多人匹配系统。

与 1.0 (app/matchmaking.py) 完全独立。
支持多人匹配：玩家指定期望人数，凑够后自动创建 v2 房间。

匹配策略：
  - 简单先到先得，按等待时间排序
  - 优先匹配 preferred_players 相同或接近的玩家
  - 凑够人数后自动创建 2.0 房间
  - 持久化到 SQLite（key 前缀 v2_match_）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from app.v2.constants import MAX_PLAYERS, MIN_PLAYERS


def _ensure_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── 队列条目 ──
@dataclass
class WaitingPlayerV2:
    player_name: str
    player_token: str           # 前端生成的匹配身份 token
    preferred_players: int      # 期望人数（MIN_PLAYERS~MAX_PLAYERS）
    joined_at: datetime = field(default_factory=_now_utc)


# ── 全局状态 ──
MATCH_QUEUE_V2: list[WaitingPlayerV2] = []
MATCH_LOCK_V2 = RLock()

# 玩家匹配状态: {player_token: {status, player_name, room_id, seat_index, room_player_token}}
PLAYER_MATCH_STATE_V2: dict[str, dict] = {}


def _persist_match_state_v2() -> None:
    """持久化 v2 匹配状态到 SQLite。"""
    from app.storage import save_kv

    queue_data = []
    for wp in MATCH_QUEUE_V2:
        queue_data.append({
            "player_name": wp.player_name,
            "player_token": wp.player_token,
            "preferred_players": wp.preferred_players,
            "joined_at": wp.joined_at.isoformat(),
        })

    save_kv("v2_match_state", {
        "queue": queue_data,
        "player_states": PLAYER_MATCH_STATE_V2,
    })


def load_match_state_v2() -> None:
    """从 SQLite 加载 v2 匹配状态。"""
    from app.storage import load_kv

    data = load_kv("v2_match_state")
    if data is None:
        return

    try:
        queue_data = data.get("queue", [])
        MATCH_QUEUE_V2.clear()
        for item in queue_data:
            MATCH_QUEUE_V2.append(WaitingPlayerV2(
                player_name=item["player_name"],
                player_token=item["player_token"],
                preferred_players=item.get("preferred_players", 4),
                joined_at=_ensure_utc(datetime.fromisoformat(item["joined_at"])),
            ))

        player_states = data.get("player_states", {})
        PLAYER_MATCH_STATE_V2.clear()
        PLAYER_MATCH_STATE_V2.update(player_states)
    except Exception as exc:
        import traceback
        print(f"[load_match_state_v2] 跳过无法兼容的旧匹配状态: {exc}")
        traceback.print_exc()
        MATCH_QUEUE_V2.clear()
        PLAYER_MATCH_STATE_V2.clear()


def enqueue_v2(
    player_name: str,
    player_token: str,
    preferred_players: int = 4,
) -> dict:
    """加入 v2 匹配队列。

    Returns:
        {matched, room_id?, seat_index?, room_player_token?, message}
    """
    global MATCH_QUEUE_V2

    with MATCH_LOCK_V2:
        # 检查是否已在队列或已匹配
        existing = PLAYER_MATCH_STATE_V2.get(player_token)
        if existing is not None:
            if existing.get("status") == "matched":
                return {
                    "matched": True,
                    "room_id": existing["room_id"],
                    "seat_index": existing.get("seat_index"),
                    "room_player_token": existing.get("room_player_token"),
                    "message": "你已经在匹配到的房间中。",
                }
            if existing.get("status") == "queued":
                return {
                    "matched": False,
                    "message": "你已在匹配队列中，请等待。",
                }

        # 检查是否已在队列中（同一用户不能重复排队）
        for wp in MATCH_QUEUE_V2:
            if wp.player_token == player_token:
                return {
                    "matched": False,
                    "message": "你已在匹配队列中。",
                }

        # 入队
        preferred_players = max(MIN_PLAYERS, min(MAX_PLAYERS, preferred_players))
        wp = WaitingPlayerV2(
            player_name=player_name,
            player_token=player_token,
            preferred_players=preferred_players,
        )
        MATCH_QUEUE_V2.append(wp)

        PLAYER_MATCH_STATE_V2[player_token] = {
            "status": "queued",
            "player_name": player_name,
            "preferred_players": preferred_players,
            "joined_at": _now_utc().isoformat(),
        }
        _persist_match_state_v2()

        # 尝试匹配
        result = _try_match_v2()
        if result["matched"]:
            matched_state = PLAYER_MATCH_STATE_V2.get(player_token, {})
            result["seat_index"] = matched_state.get("seat_index")
            result["room_player_token"] = matched_state.get("room_player_token")
            return result

        queue_size = len(MATCH_QUEUE_V2)
        return {
            "matched": False,
            "message": f"已加入匹配队列。当前队列 {queue_size} 人，等待更多玩家...",
            "queue_size": queue_size,
        }


def _try_match_v2() -> dict:
    """尝试从队列中匹配玩家。

    匹配策略：
      1. 按 preferred_players 分组
      2. 同一组内按等待时间排序
      3. 凑够 preferred_players 人即创建房间
      4. 如果该组人数不够，尝试合并相邻组（preferred_players ± 1）
    """
    global MATCH_QUEUE_V2

    if len(MATCH_QUEUE_V2) < 2:
        return {"matched": False}

    # 按 preferred_players 分组
    groups: dict[int, list[WaitingPlayerV2]] = {}
    for wp in MATCH_QUEUE_V2:
        groups.setdefault(wp.preferred_players, []).append(wp)

    # 尝试每个组
    for pref, players in sorted(groups.items()):
        if len(players) >= pref:
            # 凑够人数！取前 pref 个（按等待时间最早）
            selected = sorted(players, key=lambda p: p.joined_at)[:pref]
            return _create_match_room(selected)

    # 尝试合并相邻组（向上取整）
    for pref in sorted(groups.keys()):
        merged = list(groups[pref])
        # 尝试从 pref+1 组借人
        if (pref + 1) in groups:
            merged.extend(groups[pref + 1])
        # 尝试从 pref-1 组借人
        if (pref - 1) in groups:
            merged.extend(groups[pref - 1])

        if len(merged) >= pref:
            selected = sorted(merged, key=lambda p: p.joined_at)[:pref]
            return _create_match_room(selected)

    return {"matched": False}


def _create_match_room(players: list[WaitingPlayerV2]) -> dict:
    """为匹配到的玩家创建 v2 房间。"""
    from app.v2.room_manager import create_room_v2, delete_room_v2, join_room_v2

    # 第一个玩家作为房主创建房间
    host = players[0]
    n_players = len(players)

    try:
        room, host_seat_index, host_token = create_room_v2(
            host.player_name,
            max_players=n_players,
            min_players=n_players,
            allow_spectate=True,
            public=False,
        )
    except Exception:
        import traceback
        traceback.print_exc()
        return {"matched": False}

    # 更新房主状态
    PLAYER_MATCH_STATE_V2[host.player_token] = {
        "status": "matched",
        "player_name": host.player_name,
        "room_id": room.room_id,
        "seat_index": host_seat_index,
        "room_player_token": host_token,
        "matched_at": _now_utc().isoformat(),
    }

    # 其余玩家加入房间。任何一人失败都回滚，避免生成缺人的匹配房。
    try:
        for player in players[1:]:
            _, seat_index, player_token = join_room_v2(
                room.room_id,
                player.player_name,
            )
            PLAYER_MATCH_STATE_V2[player.player_token] = {
                "status": "matched",
                "player_name": player.player_name,
                "room_id": room.room_id,
                "seat_index": seat_index,
                "room_player_token": player_token,
                "matched_at": _now_utc().isoformat(),
            }
    except Exception:
        import traceback
        traceback.print_exc()
        delete_room_v2(room.room_id)
        for player in players:
            PLAYER_MATCH_STATE_V2[player.player_token] = {
                "status": "queued",
                "player_name": player.player_name,
                "preferred_players": player.preferred_players,
                "joined_at": player.joined_at.isoformat(),
            }
        _persist_match_state_v2()
        return {"matched": False}

    # 从队列中移除已匹配的玩家
    matched_tokens = {p.player_token for p in players}
    global MATCH_QUEUE_V2
    MATCH_QUEUE_V2 = [wp for wp in MATCH_QUEUE_V2 if wp.player_token not in matched_tokens]

    _persist_match_state_v2()

    return {
        "matched": True,
        "room_id": room.room_id,
        "message": f"匹配成功！已创建 {n_players} 人房间。",
    }


def cancel_match_v2(player_token: str) -> dict:
    """取消 v2 匹配。"""
    global MATCH_QUEUE_V2

    with MATCH_LOCK_V2:
        state = PLAYER_MATCH_STATE_V2.get(player_token)
        if state is None or state.get("status") == "idle":
            return {"ok": True, "cancelled": False, "message": "当前不在匹配队列中。"}

        if state.get("status") == "matched":
            return {"ok": True, "cancelled": False, "message": "已经匹配到房间，不能取消匹配。请退出房间后再试。"}

        # 从队列中移除
        MATCH_QUEUE_V2 = [wp for wp in MATCH_QUEUE_V2 if wp.player_token != player_token]

        # 更新状态
        PLAYER_MATCH_STATE_V2[player_token] = {
            "status": "idle",
            "player_name": state.get("player_name"),
        }
        _persist_match_state_v2()

        return {"ok": True, "cancelled": True, "message": "已退出匹配队列。"}


def get_queue_status_v2() -> dict:
    """获取 v2 匹配队列状态。"""
    with MATCH_LOCK_V2:
        queue_info = []
        for wp in MATCH_QUEUE_V2:
            queue_info.append({
                "player_name": wp.player_name,
                "preferred_players": wp.preferred_players,
                "waiting_seconds": int((_now_utc() - wp.joined_at).total_seconds()),
            })

        return {
            "queue_size": len(MATCH_QUEUE_V2),
            "players": queue_info,
        }


def get_player_match_state_v2(player_token: str) -> dict:
    """获取单个玩家的 v2 匹配状态。"""
    with MATCH_LOCK_V2:
        state = PLAYER_MATCH_STATE_V2.get(player_token)
        if state is None:
            return {"status": "idle", "player_name": None}

        return {
            "status": state.get("status", "idle"),
            "player_name": state.get("player_name"),
            "room_id": state.get("room_id"),
            "seat_index": state.get("seat_index"),
            "room_player_token": state.get("room_player_token"),
        }


def cleanup_expired_match_v2(
    queued_minutes: int = 30,
    matched_hours: int = 12,
) -> dict:
    """清理过期的 v2 匹配状态。"""
    global MATCH_QUEUE_V2

    now = _now_utc()
    removed = []

    with MATCH_LOCK_V2:
        # 清理过期队列
        MATCH_QUEUE_V2 = [
            wp for wp in MATCH_QUEUE_V2
            if wp.joined_at > now - timedelta(minutes=queued_minutes)
        ]

        # 清理过期匹配状态
        to_remove = []
        for token, state in PLAYER_MATCH_STATE_V2.items():
            if state.get("status") == "queued":
                joined_str = state.get("joined_at", "")
                try:
                    joined = _ensure_utc(datetime.fromisoformat(joined_str))
                    if joined < now - timedelta(minutes=queued_minutes):
                        to_remove.append(token)
                        removed.append(token)
                except Exception:
                    to_remove.append(token)
                    removed.append(token)

            elif state.get("status") == "matched":
                matched_str = state.get("matched_at", "")
                try:
                    matched = _ensure_utc(datetime.fromisoformat(matched_str))
                    if matched < now - timedelta(hours=matched_hours):
                        to_remove.append(token)
                        removed.append(token)
                except Exception:
                    pass

        for token in to_remove:
            del PLAYER_MATCH_STATE_V2[token]

        _persist_match_state_v2()

    return {"removed": removed}
