"""
ClapClap 2.0 状态 API — 生成房间和对局状态载荷。

与 1.0 (app/state_api.py) 完全独立。
载荷结构以「玩家列表」替代 p1/p2 双人字段。
"""

from __future__ import annotations

from app.v2.constants import ATTACK_MOVES, DEFENSE_MOVES, Move, RESOURCE_MOVES, TRICK_MOVES
from app.v2.constants import SPEED_LAYER_NAMES
from app.v2.game import GameEngineV2
from app.v2.models import (
    DecisionRequest,
    GameStateV2,
    PlayerStateV2,
    SettlementStepResult,
)
from app.v2.room import RoomV2


def _sanitize_game_payload_for_requester(
    payload: dict,
    requester_player_id: str | None,
) -> dict:
    """Remove private per-player fields before sending state to clients."""
    sanitized = dict(payload)
    players = []
    for player_data in payload.get("players", []):
        item = dict(player_data)
        can_see_own_private = (
            requester_player_id is not None
            and item.get("player_id") == requester_player_id
        )
        move_revealed = bool(item.get("move_revealed"))

        if not can_see_own_private and not move_revealed:
            item["pending_move"] = None
        for field in ("target_intent", "target_final"):
            if not can_see_own_private:
                item[field] = []
        players.append(item)

    sanitized["players"] = players
    return sanitized


# ═══════════════════════════════════════════════════════════════
# 动作目录
# ═══════════════════════════════════════════════════════════════

def get_move_catalog_v2() -> list[dict]:
    """获取动作目录（与 1.0 共享 Move 枚举）。"""
    result: list[dict] = []

    for move in Move:
        if move in RESOURCE_MOVES:
            category = "resource"
        elif move in ATTACK_MOVES:
            category = "attack"
        elif move in DEFENSE_MOVES:
            category = "defense"
        elif move in TRICK_MOVES:
            category = "trick"
        else:
            category = "unknown"

        result.append({
            "name": move.name,
            "label": move.value,
            "category": category,
        })

    return result


# ═══════════════════════════════════════════════════════════════
# 合法动作
# ═══════════════════════════════════════════════════════════════

def get_legal_moves_v2(player: PlayerStateV2) -> list[str]:
    """获取某个玩家的合法动作列表。"""
    legal: list[str] = []
    for move in Move:
        if GameEngineV2.can_afford(player, move):
            legal.append(move.name)
    return legal


def get_all_legal_moves_v2(state: GameStateV2) -> dict[str, list[str]]:
    """获取所有存活玩家的合法动作。{player_id: [move_name, ...]}"""
    result: dict[str, list[str]] = {}
    for p in state.alive_players():
        result[p.player_id] = get_legal_moves_v2(p)
    return result


# ═══════════════════════════════════════════════════════════════
# 游戏状态载荷
# ═══════════════════════════════════════════════════════════════

def get_game_state_v2_payload(
    state: GameStateV2,
    include_history: bool = True,
) -> dict:
    """生成 v2 游戏状态的前端载荷。"""
    payload = state.to_dict(include_history=include_history)

    # 添加每个存活玩家的合法动作
    payload["legal_moves"] = get_all_legal_moves_v2(state)

    # 添加动作目录
    payload["move_catalog"] = get_move_catalog_v2()

    # 添加快捷访问字段
    payload["alive_count"] = state.alive_count
    payload["is_game_over"] = state.is_game_over()

    return payload


# ═══════════════════════════════════════════════════════════════
# 房间载荷
# ═══════════════════════════════════════════════════════════════

def get_room_v2_payload(
    room: RoomV2,
    requester_token: str | None = None,
) -> dict:
    """生成 v2 房间的完整前端载荷。

    Args:
        room: RoomV2 实例
        requester_token: 请求者的 player_token（用于确定 my_seat_index / my_role）
    """

    # ── 确定请求者身份 ──
    my_seat_index: int | None = None
    my_role: str | None = None
    my_player_id: str | None = None

    if requester_token:
        seat = room.get_seat_by_token(requester_token)
        if seat is not None:
            my_seat_index = seat.seat_index
            my_player_id = seat.player_id
            # Step8: 死亡玩家自动转为观战态
            if room.game_state is not None:
                player = room.game_state.get_player(seat.player_id)
                if player is not None and not player.is_alive():
                    my_role = "dead_spectator"
                else:
                    my_role = "player"
            else:
                my_role = "player"
        else:
            spec = room.get_spectator_by_token(requester_token)
            if spec is not None:
                my_role = "spectator"

    # ── 构建席位列表（按席位号排序）──
    seats_payload = []
    for seat in sorted(room.seats, key=lambda s: s.seat_index):
        seat_data = {
            "seat_index": seat.seat_index,
            "username": seat.username,
            "player_id": seat.player_id,
            "ready": seat.ready,
            "online": room.is_seat_online(seat.seat_index),
            "connected": seat.connected,
            "is_host": seat.seat_index == room.host_seat_index,
        }
        # 如果有对局状态，附加上该玩家的对局信息
        if room.game_state is not None:
            player = room.game_state.get_player(seat.player_id)
            if player is not None:
                seat_data["alive"] = player.is_alive()
                seat_data["move_submitted"] = player.move_submitted
                seat_data["hp"] = player.hp
                seat_data["qi"] = player.qi
                seat_data["shield"] = player.shield
                seat_data["spark"] = player.spark
                seat_data["battery"] = player.battery
                seat_data["pickaxe"] = player.pickaxe
                seat_data["flash_used"] = player.flash_used
        seats_payload.append(seat_data)

    # ── 构建游戏状态 ──
    game_payload = None
    if room.game_state is not None:
        game_payload = get_game_state_v2_payload(room.game_state, include_history=True)
        game_payload = _sanitize_game_payload_for_requester(
            game_payload,
            requester_player_id=my_player_id,
        )

    # ── 构建观战者列表：仅下发展示信息，不暴露 spectator_token ──
    spectators_payload = [
        {
            "username": spectator.username,
            "joined_at": spectator.joined_at.isoformat() if spectator.joined_at else None,
        }
        for spectator in room.spectators
    ]

    # ── 公开重赛票数：不要把 player_token 暴露给其他客户端 ──
    rematch_votes: dict[str, bool] = {}
    for token, vote in room.rematch_votes.items():
        seat = room.get_seat_by_token(token)
        if seat is not None:
            rematch_votes[seat.player_id] = vote

    # ── 构建载荷 ──
    payload = {
        "room_id": room.room_id,
        "rule_version": room.rule_version,
        "status": room.status,

        # 席位
        "seats": seats_payload,
        "occupied_seats": sorted(room._occupied_seats()),
        "spectator_count": room.spectator_count(),
        "spectators": spectators_payload,

        # 请求者身份
        "my_seat_index": my_seat_index,
        "my_role": my_role,
        "my_player_id": my_player_id,

        # 房间配置
        "host_seat_index": room.host_seat_index,
        "max_players": room.max_players,
        "min_players": room.min_players,
        "start_condition": room.start_condition,
        "allow_spectate": room.allow_spectate,
        "public": room.public,
        "has_password": room.password is not None,

        # 对局状态
        "game": game_payload,
        "player_count": room.player_count(),

        # 聊天
        "chat_messages": room.chat_messages,

        # 对局记录
        "battle_id": room.battle_id,

        # 重赛
        "rematch_votes": rematch_votes,
    }

    return payload


# ═══════════════════════════════════════════════════════════════
# Step 6：决策与结算进度载荷
# ═══════════════════════════════════════════════════════════════

def get_decision_request_payload(request: DecisionRequest) -> dict:
    """获取单个决策请求的前端载荷。"""
    return request.to_dict()


def get_decision_requests_payload(state: GameStateV2) -> dict:
    """获取当前所有待处理决策请求的前端载荷。

    返回包含决策列表及元信息的字典。
    """
    requests = []
    for r in state.current_decision_requests:
        if hasattr(r, 'to_dict'):
            requests.append(r.to_dict())
        elif isinstance(r, dict):
            requests.append(r)

    return {
        "phase": state.phase,
        "sub_phase": state.sub_phase,
        "current_speed_layer": state.current_speed_layer,
        "speed_layer_name": SPEED_LAYER_NAMES.get(state.current_speed_layer, ""),
        "negotiation_round": state.negotiation_round,
        "decision_requests": requests,
    }


def get_settlement_progress_payload(result: SettlementStepResult) -> dict:
    """获取结算进度步骤的前端载荷。"""
    return result.to_dict()


def get_layer_events_payload(
    state: GameStateV2,
    layer: int | None = None,
) -> list[dict]:
    """获取速度层结算事件的前端载荷。

    Args:
        state: 对局状态
        layer: 速度层号。如果为 None，返回最新回合的所有事件。

    Returns:
        list of event dicts
    """
    if not state.history:
        return []

    log = state.history[-1]

    if layer is not None:
        return [
            e.to_dict() for e in log.speed_layer_events
            if e.speed_layer == layer
        ]

    return [e.to_dict() for e in log.speed_layer_events]


def get_round_summary_payload(state: GameStateV2) -> dict | None:
    """获取回合总结的前端载荷。"""
    if not state.history:
        return None

    log = state.history[-1]

    # 计算每个玩家的资源变化
    resource_changes = {}
    for pid in log.pre_snapshots:
        pre = log.pre_snapshots.get(pid, {})
        post = log.post_snapshots.get(pid, {})
        changes = {}
        for key in set(list(pre.keys()) + list(post.keys())):
            pre_val = pre.get(key, 0)
            post_val = post.get(key, 0)
            if pre_val != post_val:
                changes[key] = post_val - pre_val
        if changes:
            resource_changes[pid] = changes

    # 按速度层分组事件
    events_by_layer: dict[int, list[dict]] = {}
    for e in log.speed_layer_events:
        layer = e.speed_layer
        events_by_layer.setdefault(layer, []).append(e.to_dict())

    return {
        "round_num": log.round_num,
        "moves": log.moves,
        "resource_check": {
            "ok": log.resource_check_ok,
            "illegal": log.illegal_players,
        },
        "flashed_players": log.flashed_players,
        "three_chain": {
            "groups": log.three_chain_groups,
            "two_groups": log.two_three_chains,
        },
        "deaths": log.deaths,
        "resource_changes": resource_changes,
        "events_by_layer": {
            str(layer): events
            for layer, events in sorted(events_by_layer.items())
        },
        "pre_snapshots": log.pre_snapshots,
        "post_snapshots": log.post_snapshots,
        "winner": log.winner,
        "game_ended": log.game_ended,
        "alive_count": state.alive_count,
    }
