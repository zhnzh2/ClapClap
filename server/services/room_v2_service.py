"""
ClapClap 2.0 房间服务 — 业务逻辑 + 引擎连接。

与 1.0 (server/services/room_service.py) 完全独立。
负责 v2 房间的创建/加入/开始/提交/结算/退出等完整生命周期。
"""

from __future__ import annotations

from app.v2.constants import Move
from app.v2.constants import (
    STEP_ACTION_GAME_OVER,
    STEP_ACTION_REQUEST_DECISION,
    STEP_ACTION_ROUND_COMPLETE,
)
from app.v2.game import GameEngineV2
from app.v2.models import GameStateV2
from app.v2.room import LEAVE_QUIT, LEAVE_SURRENDER, RoomV2
from app.v2.room_manager import (
    create_room_v2,
    get_room_v2,
    join_room_v2,
    leave_room_v2,
    delete_room_v2,
    mark_seen_v2,
    persist_room_v2,
)
from app.v2.state_api import get_room_v2_payload


def _lookup_uid(username: str) -> int:
    """根据用户名查找 UID。"""
    from app.users import lookup_uid
    return lookup_uid(username)


def _try_create_battle(room: RoomV2) -> str | None:
    """尝试创建对局记录。"""
    from app.battle_recorder import create_battle

    participants: dict[str, dict] = {}
    seats: list[dict] = []
    host_payload: dict | None = None
    for seat in room.seats:
        uid = _lookup_uid(seat.username)
        is_host = seat.seat_index == room.host_seat_index
        seat_payload = {
            "seat_index": seat.seat_index,
            "player_id": seat.player_id,
            "username": seat.username,
            "uid": uid,
            "is_host": is_host,
        }
        seats.append(seat_payload)
        if is_host:
            host_payload = {
                "seat_index": seat.seat_index,
                "player_id": seat.player_id,
                "username": seat.username,
                "uid": uid,
            }
        if uid >= 0:
            participants[seat.player_id] = {
                "username": seat.username,
                "uid": uid,
                "seat_index": seat.seat_index,
                "player_id": seat.player_id,
                "is_host": is_host,
            }

    if len(participants) >= room.min_players:
        return create_battle(
            participants,
            rule_version=room.rule_version,
            mode="room",
            seats=seats,
            host=host_payload,
            room={
                "room_id": room.room_id,
                "max_players": room.max_players,
                "min_players": room.min_players,
                "start_condition": room.start_condition,
                "allow_spectate": room.allow_spectate,
                "public": room.public,
                "has_password": room.password is not None,
            },
        )
    return None


def _try_record_round(room: RoomV2) -> None:
    """尝试记录回合到对局记录。"""
    if room.battle_id is None or room.game_state is None:
        return

    from app.battle_recorder import record_round

    history = room.game_state.history
    if not history:
        return

    latest_log = history[-1]
    record_round(room.battle_id, latest_log.to_dict())


def _try_end_battle(room: RoomV2) -> None:
    """尝试结束对局记录。"""
    if room.battle_id is None or room.game_state is None:
        return

    from app.battle_recorder import end_battle

    winner = room.game_state.winner
    end_battle(room.battle_id, winner)


# ═══════════════════════════════════════════════════════════════
# 创建房间
# ═══════════════════════════════════════════════════════════════

def create_room_v2_service(
    host_name: str,
    *,
    max_players: int = 6,
    min_players: int = 2,
    start_condition: str = "host",
    allow_spectate: bool = True,
    public: bool = False,
    password: str | None = None,
) -> dict:
    """创建 2.0 多人房间。"""
    room, seat_index, player_token = create_room_v2(
        host_name.strip(),
        max_players=max_players,
        min_players=min_players,
        start_condition=start_condition,
        allow_spectate=allow_spectate,
        public=public,
        password=password,
    )

    return {
        "ok": True,
        "message": "房间创建成功。",
        "seat_index": seat_index,
        "player_token": player_token,
        "room": get_room_v2_payload(room, requester_token=player_token),
    }


# ═══════════════════════════════════════════════════════════════
# 加入房间
# ═══════════════════════════════════════════════════════════════

def join_room_v2_service(
    room_id: str,
    username: str,
    *,
    as_spectator: bool = False,
    seat_index: int | None = None,
    password: str | None = None,
) -> dict:
    """加入 2.0 房间。"""
    room, seat_index_or_none, token = join_room_v2(
        room_id,
        username.strip(),
        as_spectator=as_spectator,
        seat_index=seat_index,
        password=password,
    )

    from server.socket_events_v2 import emit_room_v2_state
    emit_room_v2_state(room_id)

    if as_spectator:
        return {
            "ok": True,
            "message": "已加入观战。",
            "spectator_token": token,
            "room": get_room_v2_payload(room, requester_token=token),
        }

    return {
        "ok": True,
        "message": "加入房间成功。",
        "seat_index": seat_index_or_none,
        "player_token": token,
        "room": get_room_v2_payload(room, requester_token=token),
    }


# ═══════════════════════════════════════════════════════════════
# 获取房间状态
# ═══════════════════════════════════════════════════════════════

def get_room_v2_service(room_id: str, player_token: str | None) -> tuple[dict, int]:
    """获取 v2 房间状态。"""
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    if player_token:
        mark_seen_v2(room_id, player_token.strip())

    payload = get_room_v2_payload(room, requester_token=player_token)

    return {
        "ok": True,
        "room": payload,
    }, 200


# ═══════════════════════════════════════════════════════════════
# 准备
# ═══════════════════════════════════════════════════════════════

def set_ready_service(room_id: str, player_token: str, ready: bool) -> tuple[dict, int]:
    """切换准备状态。"""
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    try:
        room.set_ready(player_token.strip(), ready)
        persist_room_v2(room)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400

    from server.socket_events_v2 import emit_room_v2_state
    emit_room_v2_state(room_id)

    return {
        "ok": True,
        "message": "已准备。" if ready else "已取消准备。",
        "room": get_room_v2_payload(room, requester_token=player_token),
    }, 200


# ═══════════════════════════════════════════════════════════════
# 开始对局
# ═══════════════════════════════════════════════════════════════

def start_game_service(room_id: str, player_token: str) -> tuple[dict, int]:
    """房主发起开始对局。"""
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    if not room.is_host(player_token.strip()):
        return {
            "ok": False,
            "error": "只有房主可以开始对局。",
        }, 403

    if not room.can_start():
        if room.status != "lobby":
            return {"ok": False, "error": "对局已开始或已结束。"}, 400
        if room.player_count() < room.min_players:
            return {
                "ok": False,
                "error": f"至少需要 {room.min_players} 名玩家才能开始。当前 {room.player_count()} 人。",
            }, 400
        if room.start_condition == "all_ready" and not room.all_players_ready():
            return {"ok": False, "error": "还有玩家未准备。"}, 400
        return {"ok": False, "error": "不满足开始条件。"}, 400

    try:
        room.start_game()
        room.battle_id = _try_create_battle(room)
        persist_room_v2(room)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400

    from server.socket_events_v2 import emit_room_v2_state
    emit_room_v2_state(room_id)

    return {
        "ok": True,
        "message": "对局已开始！",
        "room": get_room_v2_payload(room, requester_token=player_token),
    }, 200


# ═══════════════════════════════════════════════════════════════
# 提交动作 + 结算
# ═══════════════════════════════════════════════════════════════

def submit_move_v2_service(
    room_id: str,
    player_token: str,
    move_name: str,
) -> tuple[dict, int]:
    """提交本回合动作。如果所有人已提交，触发引擎结算。"""
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    # ── 解析动作名 ──
    try:
        move = Move[move_name]
    except KeyError:
        return {
            "ok": False,
            "error": f"未知动作名: {move_name}",
        }, 400

    # ── 身份验证 ──
    seat = room.get_seat_by_token(player_token.strip())
    if seat is None:
        return {
            "ok": False,
            "error": "身份无效，不能提交动作。",
        }, 403

    mark_seen_v2(room_id, player_token.strip())

    if room.status == "finished":
        return {"ok": False, "error": "当前对局已结束。"}, 400

    if room.status != "playing":
        return {"ok": False, "error": "对局尚未开始。"}, 400

    if room.game_state is None:
        return {"ok": False, "error": "对局状态异常。"}, 500

    # ── 资源预检查 ──
    player = room.game_state.get_player(seat.player_id)
    if player is None:
        return {"ok": False, "error": "找不到你的对局状态。"}, 500

    if not player.is_alive():
        return {"ok": False, "error": "你已淘汰，不能提交动作。"}, 400

    if not GameEngineV2.can_afford(player, move):
        return {"ok": False, "error": "当前动作不合法或资源不足。"}, 400

    # ── 提交动作 ──
    try:
        room.submit_move(player_token.strip(), move_name)
        persist_room_v2(room)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400

    # ── 检查是否全部提交 ──
    all_submitted = room.all_moves_submitted()

    if all_submitted:
        # ── 触发引擎结算（步进式 API）──
        alive = room.game_state.alive_players()
        moves: dict[str, Move] = {}
        for p in alive:
            if p.pending_move:
                try:
                    moves[p.player_id] = Move[p.pending_move]
                except KeyError:
                    pass

        if len(moves) != len(alive):
            return {
                "ok": False,
                "error": "部分玩家动作无效，请联系管理员。",
            }, 500

        try:
            state_snapshot = room.game_state.to_dict(include_history=True)
            engine = GameEngineV2(room.game_state)
            result = engine.begin_settlement(moves)
        except Exception as exc:
            room.game_state = GameStateV2.from_dict(state_snapshot)
            persist_room_v2(room)
            import traceback
            traceback.print_exc()
            return {
                "ok": False,
                "error": f"引擎结算异常: {exc}",
            }, 500

        # ── 持久化 ──
        persist_room_v2(room)

        # ── 广播进度 ──
        from server.socket_events_v2 import (
            emit_room_v2_state,
            emit_settlement_progress_v2,
        )
        emit_settlement_progress_v2(room_id, result)

        # ── 根据结算结果返回不同响应 ──
        if result.action == STEP_ACTION_REQUEST_DECISION:
            emit_room_v2_state(room_id)
            return {
                "ok": True,
                "message": "本回合结算已开始，等待玩家决策。",
                "resolved": False,
                "settlement_phase": "awaiting_decisions",
                "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
                "room": get_room_v2_payload(room, requester_token=player_token),
            }, 200

        elif result.action == STEP_ACTION_ROUND_COMPLETE:
            _handle_round_complete(room)
            from server.socket_events_v2 import emit_round_summary_v2
            emit_round_summary_v2(room_id)
            emit_room_v2_state(room_id)
            return {
                "ok": True,
                "message": "本回合已结算。",
                "resolved": True,
                "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
                "room": get_room_v2_payload(room, requester_token=player_token),
            }, 200

        elif result.action == STEP_ACTION_GAME_OVER:
            _handle_game_over(room)
            from server.socket_events_v2 import emit_round_summary_v2
            emit_round_summary_v2(room_id)
            emit_room_v2_state(room_id)
            return {
                "ok": True,
                "message": "对局已结束！",
                "resolved": True,
                "game_over": True,
                "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
                "room": get_room_v2_payload(room, requester_token=player_token),
            }, 200

        else:
            emit_room_v2_state(room_id)
            return {
                "ok": True,
                "message": "结算中。",
                "resolved": False,
                "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
                "room": get_room_v2_payload(room, requester_token=player_token),
            }, 200

    # ── 等待其他玩家 ──
    from server.socket_events_v2 import emit_room_v2_state
    emit_room_v2_state(room_id)

    return {
        "ok": True,
        "message": f"{seat.username} 已提交动作，等待其他玩家。",
        "resolved": False,
        "room": get_room_v2_payload(room, requester_token=player_token),
    }, 200


# ═══════════════════════════════════════════════════════════════
# 退出房间
# ═══════════════════════════════════════════════════════════════

def leave_room_v2_service(room_id: str, player_token: str) -> tuple[dict, int]:
    """退出 v2 房间。"""
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    try:
        new_host_token, leave_type = leave_room_v2(room_id, player_token.strip())
        persist_room_v2(room)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400

    # 如果所有参战者都离开了，删除房间
    if room.player_count() == 0:
        delete_room_v2(room_id)
        return {
            "ok": True,
            "message": "你已退出房间。房间已解散。",
        }, 200

    if room.game_state is not None and room.game_state.is_game_over():
        room.status = "finished"
        _try_end_battle(room)
        persist_room_v2(room)

    from server.socket_events_v2 import emit_room_v2_state, emit_player_left_v2, emit_host_changed_v2

    # 如果房主转移了，通知新老房主
    if new_host_token is not None:
        emit_host_changed_v2(room_id, new_host_token)

    emit_player_left_v2(room_id, player_token, leave_type)
    emit_room_v2_state(room_id)

    return {
        "ok": True,
        "message": "你已退出房间。" if leave_type == LEAVE_QUIT else "你已投降并退出。",
    }, 200


# ═══════════════════════════════════════════════════════════════
# 重赛
# ═══════════════════════════════════════════════════════════════

def rematch_vote_service(room_id: str, player_token: str, vote: bool) -> tuple[dict, int]:
    """重赛投票。"""
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    try:
        did_trigger, message = room.vote_rematch(player_token.strip(), vote)
        persist_room_v2(room)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400

    from server.socket_events_v2 import emit_room_v2_state
    emit_room_v2_state(room_id)

    return {
        "ok": True,
        "did_rematch": did_trigger,
        "message": message,
        "room": get_room_v2_payload(room, requester_token=player_token),
    }, 200


# ═══════════════════════════════════════════════════════════════
# 更换席位
# ═══════════════════════════════════════════════════════════════

def change_seat_service(room_id: str, player_token: str, new_seat_index: int) -> tuple[dict, int]:
    """更换席位号（仅限 lobby 阶段）。"""
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    try:
        room.change_seat(player_token.strip(), new_seat_index)
        persist_room_v2(room)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400

    from server.socket_events_v2 import emit_room_v2_state
    emit_room_v2_state(room_id)

    return {
        "ok": True,
        "message": f"已更换到席位 {new_seat_index}。",
        "room": get_room_v2_payload(room, requester_token=player_token),
    }, 200


# ═══════════════════════════════════════════════════════════════
# 结算后处理辅助
# ═══════════════════════════════════════════════════════════════

def _handle_round_complete(room: RoomV2) -> None:
    """回合完成的后续处理。"""
    room.clear_round_state()
    _try_record_round(room)
    persist_room_v2(room)


def _handle_game_over(room: RoomV2) -> None:
    """对局结束的后续处理。"""
    room.clear_round_state()
    room.status = "finished"
    _try_end_battle(room)
    _try_record_round(room)
    persist_room_v2(room)


# ═══════════════════════════════════════════════════════════════
# 决策提交（Step 6 交互协议）
# ═══════════════════════════════════════════════════════════════

def submit_decision_v2_service(
    room_id: str,
    player_token: str,
    decisions: dict,
) -> tuple[dict, int]:
    """提交结算中的决策（目标选择、冲突协商等）。

    Args:
        room_id: 房间 ID
        player_token: 玩家 token
        decisions: 决策数据，格式取决于 decision_type。
          例如 {"p1": ["p3"]} 表示 p1 选择目标 p3

    Returns:
        (response_dict, http_status)
    """
    room = get_room_v2(room_id)
    if room is None:
        return {
            "ok": False,
            "error": "房间不存在。",
            "error_code": "ROOM_NOT_FOUND",
        }, 404

    # ── 身份验证 ──
    seat = room.get_seat_by_token(player_token.strip())
    if seat is None:
        return {
            "ok": False,
            "error": "身份无效，不能提交决策。",
        }, 403

    if room.game_state is None:
        return {"ok": False, "error": "对局状态异常。"}, 500

    # ── 检查是否在等待决策阶段 ──
    if room.game_state.phase not in ("three_chain", "speed_layer"):
        return {"ok": False, "error": "当前不在决策阶段。"}, 400

    if not room.game_state.current_decision_requests:
        return {"ok": False, "error": "当前没有待处理的决策请求。"}, 400

    # ── 验证决策者身份 ──
    player_id = seat.player_id
    is_involved = any(
        (r.player_id if hasattr(r, 'player_id') else r.get('player_id', '')) == player_id
        for r in room.game_state.current_decision_requests
    )
    if not is_involved:
        return {"ok": False, "error": "你不需要提交决策。"}, 403

    # ── 去重：已提交过的不再接受 ──
    if player_id in room.game_state.decision_submitted_by:
        return {"ok": False, "error": "你已经提交过决策，等待其他玩家。"}, 400

    if set(decisions.keys()) - {player_id}:
        return {"ok": False, "error": "只能提交自己的决策，不能替其他玩家提交。"}, 403

    if player_id not in decisions:
        return {"ok": False, "error": "决策数据缺少当前玩家。"}, 400

    # ── 收集当前玩家决策，未凑齐前不推进引擎 ──
    room.game_state.pending_decisions[player_id] = decisions[player_id]
    room.game_state.decision_submitted_by.append(player_id)

    import time
    now = time.time()
    deadline = room.game_state.decision_deadline
    expected_players = set()
    for r in room.game_state.current_decision_requests:
        pid = r.player_id if hasattr(r, 'player_id') else r.get('player_id', '')
        if pid:
            expected_players.add(pid)
    submitted_players = set(room.game_state.decision_submitted_by)

    if deadline > 0 and now > deadline:
        # 收集所有超时未提交的玩家
        timed_out = expected_players - submitted_players

        if timed_out:
            # 为超时玩家生成默认决策
            from app.v2.game import GameEngineV2
            default_reqs = [
                r for r in room.game_state.current_decision_requests
                if (r.player_id if hasattr(r, 'player_id') else r.get('player_id', '')) in timed_out
            ]
            timeout_defaults = GameEngineV2._make_default_decisions(default_reqs)
            room.game_state.pending_decisions.update(timeout_defaults)
            room.game_state.decision_submitted_by.extend(
                pid for pid in timed_out
                if pid not in room.game_state.decision_submitted_by
            )
            submitted_players = set(room.game_state.decision_submitted_by)

    if expected_players - submitted_players:
        persist_room_v2(room)
        from server.socket_events_v2 import emit_room_v2_state
        emit_room_v2_state(room_id)
        return {
            "ok": True,
            "message": "决策已接收，等待其他玩家。",
            "resolved": False,
            "settlement_phase": "awaiting_decisions",
            "room": get_room_v2_payload(room, requester_token=player_token),
        }, 200

    decisions_to_apply = dict(room.game_state.pending_decisions)
    room.game_state.pending_decisions = {}

    # ── 调用引擎继续结算 ──
    try:
        state_snapshot = room.game_state.to_dict(include_history=True)
        engine = GameEngineV2(room.game_state)
        result = engine.continue_settlement(decisions_to_apply)
    except Exception as exc:
        room.game_state = GameStateV2.from_dict(state_snapshot)
        persist_room_v2(room)
        import traceback
        traceback.print_exc()
        return {
            "ok": False,
            "error": f"引擎结算异常: {exc}",
        }, 500

    # ── 持久化 ──
    persist_room_v2(room)

    # ── 广播进度 ──
    from server.socket_events_v2 import (
        emit_room_v2_state,
        emit_settlement_progress_v2,
    )
    emit_settlement_progress_v2(room_id, result)

    # ── 根据结算结果返回不同响应 ──
    if result.action == STEP_ACTION_REQUEST_DECISION:
        emit_room_v2_state(room_id)
        return {
            "ok": True,
            "message": "决策已接收，等待进一步协商。",
            "settlement_phase": "awaiting_decisions",
            "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
            "room": get_room_v2_payload(room, requester_token=player_token),
        }, 200

    elif result.action == STEP_ACTION_ROUND_COMPLETE:
        _handle_round_complete(room)
        from server.socket_events_v2 import emit_round_summary_v2
        emit_round_summary_v2(room_id)
        emit_room_v2_state(room_id)
        return {
            "ok": True,
            "message": "本回合已结算。",
            "resolved": True,
            "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
            "room": get_room_v2_payload(room, requester_token=player_token),
        }, 200

    elif result.action == STEP_ACTION_GAME_OVER:
        _handle_game_over(room)
        from server.socket_events_v2 import emit_round_summary_v2
        emit_round_summary_v2(room_id)
        emit_room_v2_state(room_id)
        return {
            "ok": True,
            "message": "对局已结束！",
            "game_over": True,
            "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
            "room": get_room_v2_payload(room, requester_token=player_token),
        }, 200

    else:
        emit_room_v2_state(room_id)
        return {
            "ok": True,
            "message": "结算进度已更新。",
            "progress": result.to_dict() if hasattr(result, 'to_dict') else result,
            "room": get_room_v2_payload(room, requester_token=player_token),
        }, 200
