"""
ClapClap 2.0 规则引擎测试。

覆盖所有阶段 (A~F)、所有速度层 (1~12)、特殊规则和边界情况。
"""

from __future__ import annotations

import unittest

from app.constants import Move
from app.v2.constants import (
    DEATH_BOOM_PICKAXE,
    DEATH_BOOM_RESOURCE,
    DEATH_NORMAL,
    PLAYER_ALIVE,
    PLAYER_DEAD,
    PHASE_DEATH_CHECK,
    PHASE_FINISHED,
    PHASE_FLASH,
    PHASE_RESOURCE_CHECK,
    PHASE_REVEAL,
    PHASE_SPEED_LAYER,
    PHASE_THREE_CHAIN,
    PHASE_WAITING_MOVES,
    SPEED_LAYER_CHI_SHUANGCHI,
    SPEED_LAYER_FIRE,
    SPEED_LAYER_FLASH,
    SPEED_LAYER_GI_ATTACK_STEAL,
    SPEED_LAYER_GI_NO_TARGET,
    SPEED_LAYER_GI_VS_HEIDONG,
    SPEED_LAYER_HEIDONG,
    SPEED_LAYER_PO_SHANDIAN,
    SPEED_LAYER_RESOURCES,
    SPEED_LAYER_THREE_CHAIN,
)
from app.v2.game import GameEngineV2
from app.v2.models import (
    EventType,
    GameStateV2,
    PlayerStateV2,
    RoundLogV2,
)


# ═══════════════════════════════════════════════════════════════
# 辅助方法
# ═══════════════════════════════════════════════════════════════

def _make_state(players_data: list[dict], battle_id: str = "test") -> GameStateV2:
    """快速创建 GameStateV2。"""
    players = []
    for i, pd in enumerate(players_data):
        players.append(PlayerStateV2(
            player_id=pd.get("player_id", f"p{i + 1}"),
            seat_index=i,
            username=pd.get("username", f"Player{i + 1}"),
            hp=pd.get("hp", 1),
            qi=pd.get("qi", 0),
            shield=pd.get("shield", 0),
            spark=pd.get("spark", 0),
            battery=pd.get("battery", 0),
            pickaxe=pd.get("pickaxe", 0),
            flash_used=pd.get("flash_used", 0),
        ))
    return GameStateV2(players=players, battle_id=battle_id)


def _run_round(state: GameStateV2, moves: dict[str, Move]) -> RoundLogV2:
    """快捷运行一个回合。"""
    engine = GameEngineV2(state)
    return engine.resolve_round(moves)


# ═══════════════════════════════════════════════════════════════
# 阶段 A：资源合法性检查
# ═══════════════════════════════════════════════════════════════

class TestPhaseAResourceCheck(unittest.TestCase):
    """阶段 A 测试：资源消耗、爆气/爆盾。"""

    def test_valid_move_deducts_cost(self):
        """合法动作扣除消耗。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.QI})
        # 破消耗 2 气，初始 3 → 剩余 1
        self.assertEqual(state.players[0].qi, 1)

    def test_illegal_move_kills_player(self):
        """资源不足 → 蚂蚁死亡（爆气/爆盾）。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 0},  # 不够出破
            {"player_id": "p2", "username": "B"},
        ])
        log = _run_round(state, {"p1": Move.PO, "p2": Move.QI})
        self.assertEqual(state.players[0].status, PLAYER_DEAD)
        self.assertEqual(state.players[0].death_cause, DEATH_BOOM_RESOURCE)
        self.assertIn("p1", log.illegal_players)
        # 非法玩家不参与后续结算 → P2 应该存活且无人攻击
        self.assertEqual(state.players[1].hp, 1)

    def test_both_illegal_ends_game_draw(self):
        """双方都非法 → 双败。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 0},
            {"player_id": "p2", "username": "B", "qi": 0},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.PO})
        # 双方都死亡 → 平局
        self.assertEqual(state.winner, "")

    def test_lie_yan_alternative_cost_spark(self):
        """烈焰优先消耗火种。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "spark": 2, "shield": 10},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.LIE_YAN, "p2": Move.QI})
        # 优先消耗 2 火种，不消耗盾
        self.assertEqual(state.players[0].spark, 0)
        self.assertEqual(state.players[0].shield, 10)

    def test_lie_yan_alternative_cost_shield(self):
        """烈焰火种不足时消耗盾。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "spark": 0, "shield": 10},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.LIE_YAN, "p2": Move.QI})
        self.assertEqual(state.players[0].shield, 6)  # 消耗 4 盾

    def test_shining_alternative_cost_battery(self):
        """Shining 优先消耗电池。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "battery": 2, "shield": 10},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.SHINING, "p2": Move.QI})
        self.assertEqual(state.players[0].battery, 0)
        self.assertEqual(state.players[0].shield, 10)

    def test_shining_alternative_cost_shield(self):
        """Shining 电池不足时消耗盾。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "battery": 0, "shield": 10},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.SHINING, "p2": Move.QI})
        self.assertEqual(state.players[0].shield, 4)  # 消耗 6 盾


# ═══════════════════════════════════════════════════════════════
# 阶段 B + C：亮招 + 闪
# ═══════════════════════════════════════════════════════════════

class TestPhaseBRevealAndCFlash(unittest.TestCase):
    """阶段 B/C 测试：统一亮招、闪结算。"""

    def test_reveal_marks_all_moves(self):
        """亮招后所有存活玩家 move_revealed = True。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.QI, "p2": Move.QI})
        self.assertTrue(state.players[0].move_revealed)
        self.assertTrue(state.players[1].move_revealed)

    def test_flash_player_excluded_from_settlement(self):
        """闪玩家退出结算，不参与攻击。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        log = _run_round(state, {"p1": Move.SHAN, "p2": Move.PO})
        # P1 闪退出，P2 攻击找不到目标（P1 已操作 + 闪）
        self.assertTrue(state.players[0].is_flashed)
        self.assertTrue(state.players[0].is_resolved())
        # P2 攻击放空
        self.assertIn("p1", log.flashed_players)

    def test_flash_uses_up_one_use(self):
        """闪消耗一次使用次数。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "flash_used": 0},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.SHAN, "p2": Move.QI})
        self.assertEqual(state.players[0].flash_used, 1)

    def test_cannot_flash_three_times(self):
        """闪最多使用 2 次，第 3 次非法。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "flash_used": 2},
            {"player_id": "p2", "username": "B"},
        ])
        log = _run_round(state, {"p1": Move.SHAN, "p2": Move.QI})
        # 第 3 次闪视为非法 → 爆气死亡
        self.assertEqual(state.players[0].status, PLAYER_DEAD)
        self.assertIn("p1", log.illegal_players)


# ═══════════════════════════════════════════════════════════════
# 阶段 D：三连
# ═══════════════════════════════════════════════════════════════

class TestPhaseDThreeChain(unittest.TestCase):
    """阶段 D 测试：三连检测与结算。"""

    def test_type1_gi_chi_po(self):
        """类型一：gi — 你吃 — 破。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 2},
            {"player_id": "p3", "username": "C", "qi": 3},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.CHI, "p3": Move.PO})
        self.assertTrue(state.three_chain_result.found)
        # 三人全部已操作
        self.assertTrue(all(p.is_resolved() for p in state.players))

    def test_type2_gi_heidong_other(self):
        """类型二：gi — 黑洞 — 其它攻击。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 9},
            {"player_id": "p3", "username": "C", "qi": 3},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.HEI_DONG, "p3": Move.PO})
        self.assertTrue(state.three_chain_result.found)
        self.assertTrue(all(p.is_resolved() for p in state.players))

    def test_flash_player_excluded_from_three_chain(self):
        """闪玩家不参与三连检测。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},              # 闪
            {"player_id": "p2", "username": "B", "qi": 2},    # gi
            {"player_id": "p3", "username": "C", "qi": 2},    # 你吃
            {"player_id": "p4", "username": "D", "qi": 3},    # 破
        ])
        _run_round(state, {
            "p1": Move.SHAN, "p2": Move.GI,
            "p3": Move.CHI, "p4": Move.PO,
        })
        # P2/P3/P4 组成三连（P1 闪排除）
        self.assertTrue(state.three_chain_result.found)

    def test_shuangchi_counts_for_three_chain_type1(self):
        """双吃也参与类型一三连。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 3},
            {"player_id": "p3", "username": "C", "qi": 3},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.SHUANG_CHI, "p3": Move.PO})
        self.assertTrue(state.three_chain_result.found)


# ═══════════════════════════════════════════════════════════════
# 阶段 E：速度层
# ═══════════════════════════════════════════════════════════════

class TestPhaseESpeedLayers(unittest.TestCase):
    """阶段 E 测试：各速度层结算。"""

    # ── 层 3：你吃 / 双吃 ──

    def test_chi_hits_po_recoil(self):
        """你吃命中破 → 反噬 1 点伤害。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        _run_round(state, {"p1": Move.CHI, "p2": Move.PO})
        self.assertEqual(state.players[1].hp, 0)

    def test_chi_hits_lightning_nullify(self):
        """你吃命中闪电 → 闪电失效。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "shield": 4},
        ])
        _run_round(state, {"p1": Move.CHI, "p2": Move.SHAN_DIAN})
        # 闪电被吃失效，不获得电池
        self.assertEqual(state.players[1].battery, 0)

    def test_chi_miss_stays_unresolved(self):
        """你吃未命中 → 保持未操作。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.CHI, "p2": Move.QI})
        # QI 不是你吃的目标
        self.assertFalse(state.players[0].is_resolved())

    def test_shuangchi_splits_into_two_chi(self):
        """双吃拆分为 2 个你吃。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B", "qi": 3},
            {"player_id": "p3", "username": "C", "qi": 3},
        ])
        _run_round(state, {
            "p1": Move.SHUANG_CHI, "p2": Move.PO, "p3": Move.PO,
        })
        # 双吃拆分为 2 个你吃，P2 和 P3 都出破 → 双吃命中两个破
        # P2 和 P3 都反噬 1 点伤害
        self.assertTrue(state.players[0].is_resolved())

    # ── 层 4：gi 攻击黑洞 ──

    def test_gi_vs_heidong_recoil_3_damage(self):
        """gi 攻击黑洞 → 3 点反噬。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 9, "hp": 3},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.HEI_DONG})
        # P2 受 3 点反噬 → HP 从 3 变为 0
        self.assertEqual(state.players[1].hp, 0)

    # ── 层 5：黑洞 ──

    def test_heidong_3_split_damage(self):
        """黑洞拆 3 段，每段 1 点伤害。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 9},
            {"player_id": "p2", "username": "B", "hp": 3},
        ])
        _run_round(state, {"p1": Move.HEI_DONG, "p2": Move.QI})
        self.assertEqual(state.players[1].hp, 0)

    # ── 层 8：gi 攻击/抢镐 ──

    def test_gi_steal_pickaxe(self):
        """gi 抢镐。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.GAO})
        # P1 抢到镐，P2 被抢
        self.assertEqual(state.players[0].pickaxe, 1)
        self.assertEqual(state.players[1].pickaxe, 0)

    def test_gi_attack_normal(self):
        """gi 攻击造成 1 点伤害。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.QI})
        self.assertEqual(state.players[1].hp, 0)

    # ── 层 10：Fire ──

    def test_fire_gives_spark(self):
        """Fire 获得 1 火种。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "shield": 3},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.FIRE, "p2": Move.QI})
        self.assertEqual(state.players[0].spark, 1)

    # ── 层 11：gi 无目标 ──

    def test_gi_no_target(self):
        """gi 无合法目标 → 失效，保持未操作。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 2},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.GI})
        # 双方 gi 都无目标
        self.assertFalse(state.players[0].is_resolved())
        self.assertFalse(state.players[1].is_resolved())

    # ── 层 12：气/盾/加镐 ──

    def test_qi_gain(self):
        """气获得 1 气。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.QI, "p2": Move.QI})
        self.assertEqual(state.players[0].qi, 1)
        self.assertEqual(state.players[1].qi, 1)

    def test_shield_gain(self):
        """盾获得 1 盾。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.SHIELD, "p2": Move.SHIELD})
        self.assertEqual(state.players[0].shield, 1)

    def test_gao_gain(self):
        """加镐获得 1 镐。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.GAO, "p2": Move.QI})
        self.assertEqual(state.players[0].pickaxe, 1)


# ═══════════════════════════════════════════════════════════════
# 阶段 F：死亡与胜负
# ═══════════════════════════════════════════════════════════════

class TestPhaseFDeathAndWinner(unittest.TestCase):
    """阶段 F 测试：死亡判定、胜负、名次。"""

    def test_last_alive_wins(self):
        """最后存活者获胜。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.QI})
        self.assertEqual(state.winner, "p1")
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.phase, PHASE_FINISHED)

    def test_simultaneous_death_draw(self):
        """同回合全员死亡 → 平局。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 0},
            {"player_id": "p2", "username": "B", "qi": 0},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.PO})
        self.assertEqual(state.winner, "")

    def test_rank_assignment(self):
        """名次分配：存活者第一，后死者靠前。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.QI})
        self.assertEqual(state.players[0].final_rank, 1)   # 存活
        self.assertEqual(state.players[1].final_rank, 2)   # 死亡

    def test_round_history_recorded(self):
        """每回合写入历史。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.QI, "p2": Move.QI})
        self.assertEqual(len(state.history), 1)
        self.assertEqual(state.history[0].round_num, 1)


# ═══════════════════════════════════════════════════════════════
# 镐系统
# ═══════════════════════════════════════════════════════════════

class TestPickaxeSystem(unittest.TestCase):
    """镐系统测试：抵挡、复活、爆镐。"""

    def test_pickaxe_blocks_damage(self):
        """镐抵挡伤害（1 镐挡 1 伤）。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B", "pickaxe": 1},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.QI})
        # P2 有 1 镐 → 挡住 1 伤害 → HP 保持 1
        self.assertEqual(state.players[1].hp, 1)
        self.assertEqual(state.players[1].pickaxe, 0)

    def test_pickaxe_revive(self):
        """HP ≤ 0 时获得镐 → 复活（恢复 1 HP，不获得镐实体）。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B", "pickaxe": 1, "hp": 0, "qi": 3},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.GAO})
        # P2 被攻击（镐挡住），层 12 加镐 → HP ≤ 0 → 复活
        self.assertEqual(state.players[1].hp, 1)
        self.assertEqual(state.players[1].pickaxe, 0)  # 复活不获得镐实体

    def test_pickaxe_boom(self):
        """镐 > 1 → 爆镐死亡。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2, "pickaxe": 1},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.GAO})
        # P1 gi 抢镐 → pickaxe 从 1 变成 2 → 爆镐
        self.assertEqual(state.players[0].status, PLAYER_DEAD)
        self.assertEqual(state.players[0].death_cause, DEATH_BOOM_PICKAXE)


# ═══════════════════════════════════════════════════════════════
# gi 特殊规则
# ═══════════════════════════════════════════════════════════════

class TestGiSpecialRules(unittest.TestCase):
    """gi 特殊规则测试。"""

    def test_gi_cannot_attack_gi(self):
        """gi 不能攻击 gi。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 2},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.GI})
        # 双方 gi 都无合法目标 → 未操作
        self.assertFalse(state.players[0].is_resolved())
        self.assertFalse(state.players[1].is_resolved())

    def test_gi_forced_attack_when_target_exists(self):
        """有合法目标时 gi 必须攻击，不能放空。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B"},
            {"player_id": "p3", "username": "C"},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.QI, "p3": Move.QI})
        # P1 gi 必须攻击 P2 或 P3（不能是 gi）
        self.assertTrue(state.players[0].is_resolved())

    def test_gi_steals_from_gao_player(self):
        """gi 抢镐成功的玩家不获得镐。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.GAO})
        self.assertEqual(state.players[1].pickaxe, 0)


# ═══════════════════════════════════════════════════════════════
# 多人场景
# ═══════════════════════════════════════════════════════════════

class TestMultiPlayer(unittest.TestCase):
    """多人（3+）场景测试。"""

    def test_three_player_mixed(self):
        """3 人对局：破 + 气 + 盾。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
            {"player_id": "p3", "username": "C"},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.QI, "p3": Move.SHIELD})
        # P1 攻击 P2（第一个合法目标）
        self.assertEqual(state.players[1].hp, 0)
        self.assertEqual(state.players[0].qi, 1)   # 消耗 2
        self.assertEqual(state.players[2].shield, 1)

    def test_four_player_two_die(self):
        """4 人对局：两两对战。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
            {"player_id": "p3", "username": "C", "qi": 3},
            {"player_id": "p4", "username": "D"},
        ])
        _run_round(state, {
            "p1": Move.PO, "p2": Move.QI,
            "p3": Move.PO, "p4": Move.QI,
        })
        # 声明驱动后，P3 的第一个合法目标是 P1，不会重新选择 P4。
        self.assertEqual(state.get_player("p2").hp, 0)
        self.assertEqual(state.get_player("p4").hp, 1)
        self.assertTrue(state.get_player("p3").is_resolved())

    def test_six_player_all_qi(self):
        """6 人对局：全部出气。"""
        players_data = [
            {"player_id": f"p{i + 1}", "username": chr(65 + i)}
            for i in range(6)
        ]
        state = _make_state(players_data)
        moves = {f"p{i + 1}": Move.QI for i in range(6)}
        _run_round(state, moves)
        for p in state.players:
            self.assertEqual(p.qi, 1)


# ═══════════════════════════════════════════════════════════════
# 声明驱动冲突
# ═══════════════════════════════════════════════════════════════

class TestDeclarationDrivenConflicts(unittest.TestCase):
    """目标声明和冲突解决应实际影响结算。"""

    def test_multi_attack_conflict_clears_non_chosen_attacker_target(self):
        """多攻少默认只保留第一个攻击者，其余攻击者放空。"""
        state = _make_state([
            {"player_id": "p3", "username": "C", "hp": 2},
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])

        _run_round(state, {"p1": Move.PO, "p2": Move.PO, "p3": Move.QI})

        p3 = state.get_player("p3")
        p1 = state.get_player("p1")
        p2 = state.get_player("p2")
        self.assertEqual(p3.hp, 1)
        self.assertTrue(p1.is_resolved())
        self.assertFalse(p2.is_resolved())
        self.assertEqual(state.target_declarations["p2"].targets, [""])
        self.assertTrue(any(c.conflict_type == "multi_attack" for c in state.current_conflicts))

    def test_mutual_attack_conflict_keeps_targets_for_nullification(self):
        """互攻不应被自动清空；同攻击力互指应对掉。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3, "hp": 2},
            {"player_id": "p2", "username": "B", "qi": 3, "hp": 2},
        ])

        _run_round(state, {"p1": Move.PO, "p2": Move.PO})

        self.assertEqual(state.players[0].hp, 2)
        self.assertEqual(state.players[1].hp, 2)
        self.assertTrue(state.players[0].is_resolved())
        self.assertTrue(state.players[1].is_resolved())
        self.assertTrue(any(c.conflict_type == "mutual" for c in state.current_conflicts))

    def test_shining_uses_declared_split_targets(self):
        """Shining 在层 6 声明的两个目标应在层 9 被逐段结算。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "battery": 2},
            {"player_id": "p2", "username": "B", "hp": 2},
            {"player_id": "p3", "username": "C", "hp": 2},
        ])

        _run_round(state, {"p1": Move.SHINING, "p2": Move.QI, "p3": Move.QI})

        self.assertEqual(state.get_player("p2").hp, 1)
        self.assertEqual(state.get_player("p3").hp, 1)
        self.assertTrue(state.get_player("p1").is_resolved())

    def test_current_conflicts_reset_each_round(self):
        """下一回合无目标冲突时不应残留上一回合的 current_conflicts。"""
        state = _make_state([
            {"player_id": "p3", "username": "C", "hp": 2},
            {"player_id": "p1", "username": "A", "qi": 6},
            {"player_id": "p2", "username": "B", "qi": 6},
        ])

        _run_round(state, {"p1": Move.PO, "p2": Move.PO, "p3": Move.QI})
        self.assertTrue(state.current_conflicts)

        _run_round(state, {"p1": Move.QI, "p2": Move.QI, "p3": Move.QI})
        self.assertEqual(state.current_conflicts, [])

    def test_multi_trick_conflict_clears_non_chosen_trickster_target(self):
        """锦囊多对一默认只保留第一个锦囊使用者，其余放空。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},     # 你吃
            {"player_id": "p2", "username": "B", "qi": 3},     # 你吃
            {"player_id": "p3", "username": "C", "qi": 3},     # 破（两个你吃的目标）
        ])
        _run_round(state, {"p1": Move.CHI, "p2": Move.CHI, "p3": Move.PO})

        # 两个你吃都指向破 → 多对一冲突
        self.assertTrue(any(
            c.conflict_type == "multi_trick"
            for c in state.current_conflicts
        ))
        # P3 只被第一个你吃（P1）选中
        declarations = state.target_declarations
        self.assertNotEqual(declarations["p1"].targets[0], "")
        self.assertEqual(declarations["p2"].targets[0], "")
        # P3 应被 P1 的你吃命中（反噬1点）
        self.assertEqual(state.players[2].hp, 0)

    def test_conflict_resolution_logged_in_events(self):
        """冲突解决应写入速度层事件。"""
        state = _make_state([
            {"player_id": "p3", "username": "C", "hp": 2},
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        log = _run_round(state, {"p1": Move.PO, "p2": Move.PO, "p3": Move.QI})

        # 检查事件中包含冲突解决
        resolved_events = [
            e for e in log.speed_layer_events
            if "冲突解决" in e.detail
        ]
        self.assertTrue(len(resolved_events) > 0)
        self.assertIn("多攻少", resolved_events[0].detail)
        self.assertIn("选择接受", resolved_events[0].detail)


# ═══════════════════════════════════════════════════════════════
# 序列化
# ═══════════════════════════════════════════════════════════════

class TestSerialization(unittest.TestCase):
    """对局状态序列化往返测试。"""

    def test_round_trip_with_history(self):
        """含历史的完整序列化往返。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 5},
            {"player_id": "p2", "username": "B"},
        ])
        # 运行 2 回合
        _run_round(state, {"p1": Move.QI, "p2": Move.QI})
        _run_round(state, {"p1": Move.PO, "p2": Move.QI})

        data = state.to_dict()
        restored = GameStateV2.from_dict(data)

        self.assertEqual(restored.round_num, 2)
        self.assertEqual(restored.winner, "p1")
        self.assertEqual(len(restored.history), 2)
        # 验证历史内容
        self.assertEqual(restored.history[0].moves["p1"], "气")
        self.assertEqual(restored.history[1].moves["p1"], "破")

    def test_mid_resolution_state_serialization(self):
        """结算中的状态可以序列化（用于保存/恢复）。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3, "hp": 2},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.PO})
        # 结算后序列化
        data = state.to_dict()
        restored = GameStateV2.from_dict(data)
        # 验证声明和冲突被保存
        self.assertIsNotNone(restored.target_declarations)
        self.assertIsNotNone(restored.current_conflicts)


# ═══════════════════════════════════════════════════════════════
# 边界情况
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """边界情况测试。"""

    def test_game_already_over_raises_error(self):
        """对局已结束时不应再结算，应抛出 ValueError。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
        ])
        state.winner = "p1"
        state.phase = PHASE_FINISHED
        with self.assertRaises(ValueError):
            _run_round(state, {"p1": Move.QI, "p2": Move.QI})

    def test_defense_move_shizi(self):
        """防御手势十字提供防御力。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B", "qi": 3},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.SHI_ZI})
        # 十字防御力 3 > 破攻击力 2 → 攻击被挡住
        self.assertEqual(state.players[1].hp, 1)

    def test_defense_move_bagua(self):
        """防御手势八卦提供防御力。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B", "qi": 4},
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.BA_GUA})
        # 八卦防御力 4 > 破攻击力 2 → 攻击被挡住
        self.assertEqual(state.players[1].hp, 1)

    def test_round_log_pre_post_snapshots(self):
        """回合日志包含前后资源快照。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},
            {"player_id": "p2", "username": "B"},
        ])
        log = _run_round(state, {"p1": Move.QI, "p2": Move.QI})
        self.assertIn("p1", log.pre_snapshots)
        self.assertIn("p1", log.post_snapshots)
        self.assertEqual(log.pre_snapshots["p1"]["qi"], 0)
        self.assertEqual(log.post_snapshots["p1"]["qi"], 1)

    def test_multi_round_resource_accumulation(self):
        """多回合资源累积正确。"""
        state = _make_state([
            {"player_id": "p1", "username": "A"},
            {"player_id": "p2", "username": "B"},
        ])
        for _ in range(3):
            _run_round(state, {"p1": Move.QI, "p2": Move.QI})
        self.assertEqual(state.players[0].qi, 3)
        self.assertEqual(state.round_num, 3)

    def test_attack_after_being_resolved_in_earlier_layer(self):
        """在较早速度层被攻击变为已操作 → 在后面层不能发起攻击。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},    # gi（层 8）
            {"player_id": "p2", "username": "B", "qi": 3},    # 破（层 9）
            {"player_id": "p3", "username": "C"},              # 气
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.PO, "p3": Move.QI})
        # P1 gi（层 8）攻击 P2（层 9 的破），P1 攻击力 1 < P2 防御 2 → 攻击被挡
        # 但 P2 被攻击 → 变为已操作 → 层 9 不能攻击
        self.assertTrue(state.players[1].is_resolved())
        # P3 未被攻击 → 存活
        self.assertEqual(state.players[2].hp, 1)

    # ── 修正验证：闪电未被吃应正常攻击并获得电池 ──

    def test_lightning_not_eaten_attacks_and_gains_battery(self):
        """普通闪电（未被吃）应正常攻击并获得 1 电池。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "shield": 4},
            {"player_id": "p2", "username": "B"},
        ])
        _run_round(state, {"p1": Move.SHAN_DIAN, "p2": Move.QI})
        # 闪电攻击 P2 → P2 HP 应该为 0
        self.assertEqual(state.players[1].hp, 0)
        # 闪电未被吃 → 获得 1 电池
        self.assertEqual(state.players[0].battery, 1)

    def test_lightning_eaten_by_chi_loses_battery(self):
        """闪电被你吃命中 → 失效且不获得电池。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},       # 你吃
            {"player_id": "p2", "username": "B", "shield": 4},   # 闪电
        ])
        _run_round(state, {"p1": Move.CHI, "p2": Move.SHAN_DIAN})
        # 闪电被吃 → 不获得电池
        self.assertEqual(state.players[1].battery, 0)
        # P1 的 HP 应该不变（吃不造成伤害，只让闪电失效）
        self.assertEqual(state.players[0].hp, 1)

    # ── 修正验证：已结束对局不可再结算 ──

    def test_resolve_round_on_finished_game_raises(self):
        """对局结束后调用 resolve_round 应抛出 ValueError。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},
            {"player_id": "p2", "username": "B"},
        ])
        # 先正常结束一局
        _run_round(state, {"p1": Move.PO, "p2": Move.QI})
        self.assertTrue(state.is_game_over())
        # 再尝试结算应抛出异常
        with self.assertRaises(ValueError):
            _run_round(state, {"p1": Move.QI, "p2": Move.QI})

    # ── 修正验证：两组三连必须互不重叠 ──

    def test_two_three_chain_requires_disjoint_players(self):
        """两组三连必须由 6 名不同玩家组成。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 2},     # gi
            {"player_id": "p2", "username": "B", "qi": 2},     # 你吃
            {"player_id": "p3", "username": "C", "qi": 3},     # 破
        ])
        _run_round(state, {"p1": Move.GI, "p2": Move.CHI, "p3": Move.PO})
        # 只有 3 人，即使同时满足两种三连类型也不构成两组独立三连
        self.assertTrue(state.three_chain_result.found)
        self.assertFalse(state.three_chain_result.two_groups)

    # ── 修正验证：放空/无目标攻击者不标记已操作 ──

    def test_miss_attacker_stays_unresolved(self):
        """攻击放空的玩家应保持未操作。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 3},     # 破
            {"player_id": "p2", "username": "B"},              # 闪
        ])
        _run_round(state, {"p1": Move.PO, "p2": Move.SHAN})
        # P2 闪 → 已操作，退出结算
        # P1 的破找不到未操作目标 → 放空 → 应保持未操作
        self.assertFalse(state.players[0].is_resolved())

    def test_heidong_all_miss_stays_unresolved(self):
        """黑洞全部放空应保持未操作。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 9},     # 黑洞
            {"player_id": "p2", "username": "B"},              # 闪
        ])
        _run_round(state, {"p1": Move.HEI_DONG, "p2": Move.SHAN})
        # P2 闪 → 已操作，P1 黑洞无合法目标 → 全部放空 → 应保持未操作
        self.assertFalse(state.players[0].is_resolved())

    # ── 修正验证：资源死亡写入 log.deaths ──

    def test_resource_death_in_log_deaths(self):
        """爆气/爆盾死亡应写入 log.deaths。"""
        state = _make_state([
            {"player_id": "p1", "username": "A", "qi": 0},     # 不够出破
            {"player_id": "p2", "username": "B"},
        ])
        log = _run_round(state, {"p1": Move.PO, "p2": Move.QI})
        self.assertEqual(len(log.deaths), 1)
        self.assertEqual(log.deaths[0]["player_id"], "p1")
        self.assertEqual(log.deaths[0]["cause"], DEATH_BOOM_RESOURCE)


if __name__ == "__main__":
    unittest.main()
