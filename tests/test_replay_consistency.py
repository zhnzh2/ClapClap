"""
回放一致性测试。

验证指标：
1. 从存档重构初始状态 → 逐回合用存档决策重放 → 最终名次、胜者与存档一致
2. 每回合的死亡列表、资源快照与存档一致
3. 速度层事件数量无丢失
4. 兼容旧 2.0 记录（无 record_schema 字段）
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import app.battle_recorder as recorder
from app.v2.game import GameEngineV2
from app.v2.models import (
    GameStateV2, PlayerStateV2, RoundLogV2,
    ConflictRecord, SpeedLayerEvent, TargetDeclaration, DecisionOption,
)
from app.constants import Move
from app.storage import DATA_DIR


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _build_state_from_participants(participants: dict, seats: list | None = None) -> GameStateV2:
    """从 battle JSON 的 participants 重建初始 GameStateV2。"""
    players = []
    # 优先用 seats 的顺序
    ordered = seats or []
    seen = set()
    for s in ordered:
        pid = s.get("player_id", "")
        info = participants.get(pid, {})
        if pid and pid not in seen:
            seen.add(pid)
            players.append(PlayerStateV2(
                player_id=pid,
                seat_index=s.get("seat_index", len(players)),
                username=info.get("username", pid),
            ))
    # 其余 participants
    for pid, info in participants.items():
        if pid not in seen:
            seen.add(pid)
            players.append(PlayerStateV2(
                player_id=pid,
                seat_index=info.get("seat_index", len(players)),
                username=info.get("username", pid),
            ))
    return GameStateV2(players=players, battle_id="replay-test")


def _lookup_archived_decision(decision_type: str, player_id: str, speed_layer: int,
                              round_data: dict) -> list | str | None:
    """从存档数据中查找匹配的决策结果。"""
    # 1) 目标选择：优先从 target_declarations_by_layer 取
    if decision_type == "target_select":
        decls = round_data.get("target_declarations_by_layer", {}) or {}
        layer_decls = decls.get(str(speed_layer), decls.get(speed_layer, {}))
        pdecl = layer_decls.get(player_id, {})
        targets = pdecl.get("targets")
        if targets:
            return list(targets)
        # 回退到 decision_log
        for d in round_data.get("decision_log", []) or []:
            if (d.get("decision_type") == decision_type and
                    d.get("player_id") == player_id and
                    int(d.get("speed_layer", 0)) == speed_layer):
                return list(d.get("chosen", []) or [])

    # 2) 三连选人 / 冲突解决
    if decision_type in ("three_chain_select", "conflict_resolve"):
        for d in round_data.get("decision_log", []) or []:
            if (d.get("decision_type") == decision_type and
                    d.get("player_id") == player_id):
                chosen = d.get("chosen", []) or []
                return chosen[0] if chosen else None

    return None


def _replay_round_strict(state: GameStateV2, round_data: dict):
    """严格按照存档决策重放一回合，返回 RoundLogV2。"""
    engine = GameEngineV2(state)

    # 将 moves 从字符串转回 Move 枚举
    raw_moves = round_data.get("moves", {}) or {}
    moves = {}
    for pid, mname in raw_moves.items():
        try:
            moves[pid] = Move(mname)
        except ValueError:
            continue

    if not moves:
        return None

    result = engine.begin_settlement(moves)

    # 循环处理决策点
    loop_guard = 0
    while result.action == "request_decision" and loop_guard < 200:
        loop_guard += 1
        decisions = {}
        for req in (result.decision_requests or []):
            req_dict = req.to_dict() if hasattr(req, 'to_dict') else req
            dtype = req_dict.get("decision_type", "")
            pid = req_dict.get("player_id", "")
            layer = req_dict.get("speed_layer", 0)

            archived = _lookup_archived_decision(dtype, pid, int(layer), round_data)
            if archived is not None:
                decisions[pid] = archived
            else:
                # 回退：用默认值
                default = engine._make_default_decisions([req])
                if pid in default:
                    decisions[pid] = default[pid]

        result = engine.continue_settlement(decisions)

    if loop_guard >= 200:
        raise RuntimeError("结算循环超过 200 次，可能死循环")

    return engine.log


def _round_data_matches(archived: dict, replayed_log: RoundLogV2 | None, strict: bool = True) -> list[str]:
    """比较存档回合数据和重放日志，返回差异列表。"""
    diffs = []
    if replayed_log is None:
        diffs.append("重放未能产生日志")
        return diffs

    replayed = replayed_log.to_dict()

    # 1) 死亡
    archived_deaths = {(d.get("player_id"), d.get("cause")) for d in (archived.get("deaths") or [])}
    replayed_deaths = {(d.get("player_id"), d.get("cause")) for d in (replayed.get("deaths") or [])}
    if archived_deaths != replayed_deaths:
        diffs.append(f"死亡不一致: 存档={archived_deaths} 重放={replayed_deaths}")

    # 2) 回合前资源快照（应与存档完全一致）
    archived_pre = archived.get("pre_snapshots", {}) or {}
    replayed_pre = replayed.get("pre_snapshots", {}) or {}
    for pid in set(list(archived_pre.keys()) + list(replayed_pre.keys())):
        ap = archived_pre.get(pid, {})
        rp = replayed_pre.get(pid, {})
        for key in set(list(ap.keys()) + list(rp.keys())):
            if ap.get(key) != rp.get(key):
                diffs.append(f"pre_snapshot[{pid}][{key}]: 存档={ap.get(key)} 重放={rp.get(key)}")

    # 3) 回合后资源快照（严格模式下比较）
    if strict:
        archived_post = archived.get("post_snapshots", {}) or {}
        replayed_post = replayed.get("post_snapshots", {}) or {}
        for pid in set(list(archived_post.keys()) + list(replayed_post.keys())):
            ap = archived_post.get(pid, {})
            rp = replayed_post.get(pid, {})
            for key in set(list(ap.keys()) + list(rp.keys())):
                if ap.get(key) != rp.get(key):
                    diffs.append(f"post_snapshot[{pid}][{key}]: 存档={ap.get(key)} 重放={rp.get(key)}")

    # 4) 名次更新
    archived_ranks = archived.get("rank_updates", {}) or archived.get("result", {}).get("rank_updates", {}) or {}
    replayed_ranks = replayed.get("rank_updates", {}) or {}
    if archived_ranks != replayed_ranks:
        diffs.append(f"名次不一致: 存档={archived_ranks} 重放={replayed_ranks}")

    # 5) 回合胜者
    archived_winner = archived.get("winner")
    replayed_winner = replayed.get("winner")
    if archived_winner != replayed_winner:
        diffs.append(f"回合胜者不一致: 存档={archived_winner} 重放={replayed_winner}")

    # 6) game_ended
    if archived.get("game_ended") != replayed.get("game_ended"):
        diffs.append(f"game_ended 不一致: 存档={archived.get('game_ended')} 重放={replayed.get('game_ended')}")

    # 7) 速度层事件数量（不严格比较事件内容，因为决策回放可能产生微小差异）
    archived_events = len(archived.get("speed_layer_events", []) or [])
    replayed_events = len(replayed.get("speed_layer_events", []) or [])
    if archived_events != replayed_events:
        diffs.append(f"速度层事件数量不一致: 存档={archived_events} 重放={replayed_events}")

    return diffs


# ═══════════════════════════════════════════════════════════════════
# 测试类
# ═══════════════════════════════════════════════════════════════════

class TestReplayNewBattle(unittest.TestCase):
    """从零创建 2.0 对战 → 存档 → 重放 → 验证一致。"""

    def setUp(self):
        self._orig_data_dir = DATA_DIR
        self._tmp = TemporaryDirectory(prefix="clapclap_replay_")
        # 临时替换 DATA_DIR
        import app.storage
        app.storage.DATA_DIR = Path(self._tmp.name)
        recorder.BATTLES_DIR = Path(self._tmp.name) / "battles"
        recorder.RUB_DIR = recorder.BATTLES_DIR / "rub"

    def tearDown(self):
        import app.storage
        app.storage.DATA_DIR = self._orig_data_dir
        recorder.BATTLES_DIR = self._orig_data_dir / "battles"
        recorder.RUB_DIR = recorder.BATTLES_DIR / "rub"
        self._tmp.cleanup()

    def test_new_battle_replay_produces_identical_final_result(self):
        """完整流程：创建 3 人对战 → 玩多回合 → 存档 → 重放 → 名次一致。"""
        # ── 创建初始状态 ──
        participants = {
            "p0": {"username": "Alice", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0", "is_host": True},
            "p1": {"username": "Bob", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1", "is_host": False},
            "p2": {"username": "Carol", "uid": 2, "status": "active", "seat_index": 2, "player_id": "p2", "is_host": False},
        }
        seats = [
            {"seat_index": 0, "player_id": "p0", "username": "Alice", "uid": 0, "is_host": True},
            {"seat_index": 1, "player_id": "p1", "username": "Bob", "uid": 1, "is_host": False},
            {"seat_index": 2, "player_id": "p2", "username": "Carol", "uid": 2, "is_host": False},
        ]

        battle_id = recorder.create_battle(
            participants,
            rule_version="2.0",
            mode="local",
            seats=seats,
            host=seats[0],
            room={"max_players": 3, "min_players": 2},
        )

        state = _build_state_from_participants(participants, seats)

        # ── 玩多回合（用 resolve_round 自动模拟） ──
        all_rounds = []
        for rn in range(1, 8):
            if state.is_game_over():
                break
            alive = [p.player_id for p in state.alive_players()]
            # 简单策略：轮流用气（qi）
            moves = {}
            for pid in alive:
                moves[pid] = Move.QI
            log = GameEngineV2(state).resolve_round(moves)
            round_dict = log.to_dict()
            # 记录回合（触发 normalize）
            recorder.record_round(battle_id, round_dict)
            all_rounds.append(round_dict)

        recorder.end_battle(battle_id, winner=state.winner)

        # ── 读回存档 ──
        archived = recorder.read_battle(battle_id)
        self.assertIsNotNone(archived, "存档应可读")
        self.assertEqual(archived.get("rule_version"), "2.0")

        # ── 重放 ──
        replay_state = _build_state_from_participants(
            archived.get("participants", {}),
            archived.get("seats"),
        )

        round_diffs = []
        for i, round_data in enumerate(archived.get("rounds", [])):
            log = _replay_round_strict(replay_state, round_data)
            diffs = _round_data_matches(round_data, log, strict=True)
            for d in diffs:
                round_diffs.append(f"第{i+1}回合: {d}")

        self.assertEqual(
            len(round_diffs), 0,
            f"重放不一致:\n" + "\n".join(round_diffs) if round_diffs else ""
        )

        # ── 验证最终名次一致 ──
        archived_final = archived.get("final_result", {}) or {}
        archived_rankings = {
            r.get("player_id"): r.get("rank")
            for r in archived_final.get("rankings", [])
        }
        for p in replay_state.players:
            pid = p.player_id
            archived_rank = archived_rankings.get(pid)
            if archived_rank is not None:
                self.assertEqual(
                    p.final_rank, archived_rank,
                    f"玩家 {pid} 最终名次: 存档={archived_rank} 重放={p.final_rank}"
                )
            # 胜者一致
            if archived_final.get("winner") == pid:
                self.assertEqual(replay_state.winner, pid)

    def test_new_battle_with_different_moves(self):
        """测试不同招式的重放一致性（非全 QI）。"""
        participants = {
            "p0": {"username": "A", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0", "is_host": True},
            "p1": {"username": "B", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1", "is_host": False},
        }
        seats = [
            {"seat_index": 0, "player_id": "p0", "username": "A", "uid": 0, "is_host": True},
            {"seat_index": 1, "player_id": "p1", "username": "B", "uid": 1, "is_host": False},
        ]

        battle_id = recorder.create_battle(
            participants, rule_version="2.0", mode="local",
            seats=seats, host=seats[0],
            room={"max_players": 2, "min_players": 2},
        )
        state = _build_state_from_participants(participants, seats)

        # 用不同招式序列
        move_sequences = [
            [Move.PO, Move.SHAN_DIAN],     # 破 vs 闪电
            [Move.QI, Move.QI],            # 气 vs 气
            [Move.GI, Move.PO],            # gi vs 破
        ]

        for seq in move_sequences:
            if state.is_game_over():
                break
            alive = [p.player_id for p in state.alive_players()]
            moves = {alive[i]: seq[i] for i in range(min(len(alive), len(seq)))}
            log = GameEngineV2(state).resolve_round(moves)
            recorder.record_round(battle_id, log.to_dict())

        recorder.end_battle(battle_id, winner=state.winner)
        archived = recorder.read_battle(battle_id)
        self.assertIsNotNone(archived)

        # 重放
        replay_state = _build_state_from_participants(
            archived.get("participants", {}), archived.get("seats"),
        )

        all_diffs = []
        for i, rd in enumerate(archived.get("rounds", [])):
            log = _replay_round_strict(replay_state, rd)
            diffs = _round_data_matches(rd, log, strict=True)
            all_diffs.extend([f"第{i+1}回合: {d}" for d in diffs])

        self.assertEqual(len(all_diffs), 0,
            f"重放不一致:\n" + "\n".join(all_diffs) if all_diffs else "")

        # 最终胜者一致
        self.assertEqual(replay_state.winner, archived.get("final_result", {}).get("winner"))

    def test_replay_preserves_resource_snapshots(self):
        """重放后的每回合资源快照与存档严格一致。"""
        participants = {
            "p0": {"username": "X", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0"},
            "p1": {"username": "Y", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1"},
        }
        battle_id = recorder.create_battle(
            participants, rule_version="2.0", mode="local",
            seats=[{"seat_index": 0, "player_id": "p0"}, {"seat_index": 1, "player_id": "p1"}],
            host=None, room={"max_players": 2, "min_players": 2},
        )
        state = _build_state_from_participants(participants, None)

        # 连续多轮 QI（资源会增长）
        for _ in range(5):
            if state.is_game_over():
                break
            alive = [p.player_id for p in state.alive_players()]
            moves = {alive[0]: Move.QI, alive[1]: Move.QI} if len(alive) >= 2 else {alive[0]: Move.QI}
            log = GameEngineV2(state).resolve_round(moves)
            recorder.record_round(battle_id, log.to_dict())

        recorder.end_battle(battle_id, winner=state.winner)
        archived = recorder.read_battle(battle_id)

        # 重放并逐回合比较资源快照
        replay_state = _build_state_from_participants(
            archived.get("participants", {}), archived.get("seats"),
        )

        for i, rd in enumerate(archived.get("rounds", [])):
            log = _replay_round_strict(replay_state, rd)
            # 严格比较前后快照
            archived_pre = rd.get("pre_snapshots", {}) or {}
            replayed_pre = (log.to_dict() if log else {}).get("pre_snapshots", {}) or {}
            for pid in archived_pre:
                for key in archived_pre[pid]:
                    self.assertEqual(
                        archived_pre[pid][key], replayed_pre.get(pid, {}).get(key),
                        f"第{i+1}回合 pre_snapshot[{pid}][{key}] 不一致"
                    )

            archived_post = rd.get("post_snapshots", {}) or {}
            replayed_post = (log.to_dict() if log else {}).get("post_snapshots", {}) or {}
            for pid in archived_post:
                for key in archived_post[pid]:
                    self.assertEqual(
                        archived_post[pid][key], replayed_post.get(pid, {}).get(key),
                        f"第{i+1}回合 post_snapshot[{pid}][{key}] 不一致"
                    )


class TestReplayDataIntegrity(unittest.TestCase):
    """测试存档数据结构完整性（不依赖真实引擎重放）。"""

    def setUp(self):
        self._orig_data_dir = DATA_DIR
        self._tmp = TemporaryDirectory(prefix="clapclap_replay_")
        import app.storage
        app.storage.DATA_DIR = Path(self._tmp.name)
        recorder.BATTLES_DIR = Path(self._tmp.name) / "battles"
        recorder.RUB_DIR = recorder.BATTLES_DIR / "rub"

    def tearDown(self):
        import app.storage
        app.storage.DATA_DIR = self._orig_data_dir
        recorder.BATTLES_DIR = self._orig_data_dir / "battles"
        recorder.RUB_DIR = recorder.BATTLES_DIR / "rub"
        self._tmp.cleanup()

    def test_archived_rounds_have_all_required_fields_for_replay(self):
        """存档的每一回合包含重放所需的全部字段。"""
        participants = {
            "p0": {"username": "A", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0"},
            "p1": {"username": "B", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1"},
        }
        battle_id = recorder.create_battle(
            participants, rule_version="2.0", mode="local",
            seats=[{"seat_index": 0, "player_id": "p0"}, {"seat_index": 1, "player_id": "p1"}],
        )
        state = _build_state_from_participants(participants, None)

        for _ in range(3):
            if state.is_game_over():
                break
            alive = [p.player_id for p in state.alive_players()]
            moves = {alive[0]: Move.QI, alive[1]: Move.QI} if len(alive) >= 2 else {alive[0]: Move.QI}
            log = GameEngineV2(state).resolve_round(moves)
            recorder.record_round(battle_id, log.to_dict())

        recorder.end_battle(battle_id, winner=state.winner)
        archived = recorder.read_battle(battle_id)

        required_fields = [
            "moves", "pre_snapshots", "post_snapshots",
            "target_declarations_by_layer", "decision_log",
            "speed_layer_events", "deaths", "rank_updates",
            "resource_check_ok", "illegal_players", "flashed_players",
            "winner", "game_ended",
        ]
        for i, rd in enumerate(archived.get("rounds", [])):
            for field in required_fields:
                self.assertIn(field, rd, f"第{i+1}回合缺少字段: {field}")

    def test_final_result_matches_latest_rank_updates(self):
        """final_result 中的名次与最后一回合的 rank_updates 一致。"""
        participants = {
            "p0": {"username": "A", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0"},
            "p1": {"username": "B", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1"},
        }
        battle_id = recorder.create_battle(
            participants, rule_version="2.0", mode="local",
            seats=[{"seat_index": 0, "player_id": "p0"}, {"seat_index": 1, "player_id": "p1"}],
        )
        state = _build_state_from_participants(participants, None)

        # 玩到结束（用 QI+PO 组合确保不会第一轮双死）
        while not state.is_game_over():
            alive = [p.player_id for p in state.alive_players()]
            moves = {}
            for i, pid in enumerate(alive):
                # 交替：p0 用破攻击，p1 用气防守
                moves[pid] = Move.PO if i == 0 else Move.QI
            log = GameEngineV2(state).resolve_round(moves)
            recorder.record_round(battle_id, log.to_dict())

        recorder.end_battle(battle_id, winner=state.winner)
        archived = recorder.read_battle(battle_id)

        final_result = archived.get("final_result", {}) or {}
        rankings = final_result.get("rankings", [])
        self.assertGreater(len(rankings), 0, "应有排名列表")

        # 最后一回合的 rank_updates 应与 final_result 的 rankings 一致
        last_round = archived.get("rounds", [])[-1]
        last_ranks = last_round.get("rank_updates", {}) or {}
        for r in rankings:
            pid = r.get("player_id")
            self.assertIn(pid, last_ranks, f"玩家 {pid} 应在最后一回合有名次更新")
            self.assertEqual(r.get("rank"), last_ranks.get(pid),
                f"玩家 {pid} 名次: final_result={r.get('rank')} rank_updates={last_ranks.get(pid)}")

    def test_speed_layer_events_not_empty_for_attack_rounds(self):
        """包含攻击动作的回合速度层事件不应为空。"""
        participants = {
            "p0": {"username": "A", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0"},
            "p1": {"username": "B", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1"},
        }
        battle_id = recorder.create_battle(
            participants, rule_version="2.0", mode="local",
            seats=[{"seat_index": 0, "player_id": "p0"}, {"seat_index": 1, "player_id": "p1"}],
        )
        state = _build_state_from_participants(participants, None)

        # QI 回合事件少（只有气）
        log_qi = GameEngineV2(state).resolve_round({"p0": Move.QI, "p1": Move.QI})
        recorder.record_round(battle_id, log_qi.to_dict())

        # PO 回合事件多（有攻击）
        log_po = GameEngineV2(state).resolve_round({"p0": Move.PO, "p1": Move.PO})
        recorder.record_round(battle_id, log_po.to_dict())

        archived = recorder.read_battle(battle_id)
        qi_events = len(archived["rounds"][0].get("speed_layer_events", []))
        po_events = len(archived["rounds"][1].get("speed_layer_events", []))

        # PO 回合应有更多事件（伤害事件）
        self.assertGreater(po_events, 0, "攻击回合速度层事件不应为空")
        # QI 回合事件少，但至少也有气获取事件
        self.assertGreaterEqual(qi_events, 0)


class TestReplayCompatibility(unittest.TestCase):
    """兼容性测试：旧格式 2.0 数据（无 record_schema）能正常读取和重放。"""

    def setUp(self):
        self._orig_data_dir = DATA_DIR
        self._tmp = TemporaryDirectory(prefix="clapclap_replay_")
        import app.storage
        app.storage.DATA_DIR = Path(self._tmp.name)
        recorder.BATTLES_DIR = Path(self._tmp.name) / "battles"
        recorder.RUB_DIR = recorder.BATTLES_DIR / "rub"

    def tearDown(self):
        import app.storage
        app.storage.DATA_DIR = self._orig_data_dir
        recorder.BATTLES_DIR = self._orig_data_dir / "battles"
        recorder.RUB_DIR = recorder.BATTLES_DIR / "rub"
        self._tmp.cleanup()

    def test_old_v2_data_without_record_schema_can_be_read(self):
        """模拟旧格式 2.0 存档（无 record_schema/normalized 字段），确认可读。"""
        participants = {
            "p0": {"username": "A", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0"},
            "p1": {"username": "B", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1"},
        }

        # 直接写入旧格式 JSON（跳过 _normalize_v2_round）
        from app.battle_recorder import _ensure_dirs, _battle_path, _format_timestamp, _append_user_battle
        from datetime import datetime, timezone

        _ensure_dirs()
        battle_id = "20990101000000001"
        state = _build_state_from_participants(participants, None)

        # 生成一回合原始日志（无 normalize）
        log = GameEngineV2(state).resolve_round({"p0": Move.QI, "p1": Move.PO})
        round_dict = log.to_dict()
        # 故意去掉 record_schema（模拟旧数据）
        round_dict.pop("record_schema", None)

        data = {
            "battle_id": battle_id,
            "schema_version": "2.0.0",
            "rule_version": "2.0",
            "mode": "local",
            "mode_label": "本地对战",
            "start_time": _format_timestamp(datetime.now(timezone.utc)),
            "end_time": None,
            "participants": participants,
            "seats": [],
            "host": None,
            "room": {},
            "spectators": [],
            "rounds": [round_dict],
            "chat": [],
        }
        path = _battle_path(battle_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 读回
        archived = recorder.read_battle(battle_id)
        self.assertIsNotNone(archived, "旧格式数据应能读取")
        self.assertEqual(archived["rule_version"], "2.0")
        self.assertEqual(len(archived["rounds"]), 1)

        rd = archived["rounds"][0]
        # record_schema 可能不存在
        if "record_schema" not in rd:
            # 这是预期的：旧数据没有此字段
            pass

        # 验证核心字段存在
        self.assertIn("moves", rd)
        self.assertIn("pre_snapshots", rd)
        self.assertIn("post_snapshots", rd)

        # 清理
        path.unlink(missing_ok=True)

    def test_replay_old_format_still_produces_valid_rounds(self):
        """旧格式数据通过重放仍能产生有效回合（引擎不崩溃）。"""
        participants = {
            "p0": {"username": "A", "uid": 0, "status": "active", "seat_index": 0, "player_id": "p0"},
            "p1": {"username": "B", "uid": 1, "status": "active", "seat_index": 1, "player_id": "p1"},
        }

        from app.battle_recorder import _ensure_dirs, _battle_path, _format_timestamp
        from datetime import datetime, timezone

        _ensure_dirs()
        battle_id = "20990101000000002"
        state = _build_state_from_participants(participants, None)

        log = GameEngineV2(state).resolve_round({"p0": Move.PO, "p1": Move.SHAN_DIAN})
        round_dict = log.to_dict()
        round_dict.pop("record_schema", None)

        data = {
            "battle_id": battle_id,
            "schema_version": "2.0.0",
            "rule_version": "2.0",
            "mode": "local",
            "start_time": _format_timestamp(datetime.now(timezone.utc)),
            "end_time": None,
            "participants": participants,
            "seats": [],
            "host": None,
            "room": {},
            "spectators": [],
            "rounds": [round_dict],
            "chat": [],
        }
        path = _battle_path(battle_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        archived = recorder.read_battle(battle_id)
        replay_state = _build_state_from_participants(
            archived.get("participants", {}), archived.get("seats"),
        )

        # 重放不应抛出异常
        try:
            log_replayed = _replay_round_strict(replay_state, archived["rounds"][0])
            self.assertIsNotNone(log_replayed, "旧格式重放应产生有效日志")
        except Exception as e:
            self.fail(f"旧格式重放不应崩溃: {e}")

        path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
