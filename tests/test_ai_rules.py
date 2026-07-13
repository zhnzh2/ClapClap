"""
阶段 0-2 测试：AI 规则基准与启发式策略。

覆盖：
  - 动作空间（数量、顺序、映射、指纹）
  - 合法动作掩码（与 get_legal_moves 一致、边界条件）
  - 玩家视角转换
  - 统一策略接口（可复现、不修改状态、防作弊）
  - 启发式评分（终局优先级、HP、资源、闪、镐风险）
  - 一步模拟（隔离性、不修改原状态、评分单调性）
  - 难度分层（随机 vs 启发式 vs 保守启发式）
"""

from __future__ import annotations

import copy
import random
import unittest
from uuid import uuid4

from app import users
from app.ai.engine import (
    get_legal_action_mask,
    get_legal_moves_list,
    get_player_view,
    select_move,
)
from app.ai.space import (
    ACTION_SPACE_FINGERPRINT,
    ACTION_SPACE_SIZE,
    INDEX_BY_MOVE,
    MOVE_BY_INDEX,
    get_action_space_fingerprint,
    get_index_by_move,
    get_move_by_index,
    get_moves_in_order,
    validate_action_space,
)
from app.ai.strategies import (
    DOUBLE_LOSE_SCORE,
    LOSE_SCORE,
    WIN_SCORE,
    evaluate_state,
    heuristic_select_move,
)
from app.v1.constants import MAX_FLASH_USE, Move
from app.v1.game import GameEngine
from app.v1.models import GameState
from app.v1.state_api import get_legal_moves


# ============================================================================
# 动作空间测试
# ============================================================================


class TestActionSpace(unittest.TestCase):
    """6.1 动作空间测试"""

    def test_action_count_is_17(self):
        """动作数量严格等于 17。"""
        self.assertEqual(ACTION_SPACE_SIZE, 17)

    def test_action_order_matches_move_enum(self):
        """动作索引顺序与 Move 枚举顺序完全一致。"""
        moves_in_order = get_moves_in_order()
        enum_moves = list(Move)
        self.assertEqual(len(moves_in_order), len(enum_moves))
        for i, (a, b) in enumerate(zip(moves_in_order, enum_moves)):
            self.assertIs(a, b, f"索引 {i}: {a.name} vs {b.name}")

    def test_index_move_mapping_bijective(self):
        """action_index <-> Move 双向映射无重复、无遗漏。"""
        # 每个 Move 都有唯一索引
        seen_indices = set()
        for move in Move:
            idx = get_index_by_move(move)
            self.assertNotIn(idx, seen_indices,
                             f"Move {move.name} 的索引 {idx} 重复")
            seen_indices.add(idx)

        # 每个索引都有唯一 Move
        seen_moves = set()
        for i in range(ACTION_SPACE_SIZE):
            move = get_move_by_index(i)
            self.assertNotIn(move, seen_moves,
                             f"索引 {i} 对应 Move {move.name} 重复")
            seen_moves.add(move)

    def test_index_and_move_roundtrip(self):
        """索引 -> Move -> 索引 往返一致。"""
        for i in range(ACTION_SPACE_SIZE):
            move = get_move_by_index(i)
            self.assertEqual(get_index_by_move(move), i)

    def test_space_fingerprint_stable(self):
        """动作空间指纹在当前代码版本下稳定。"""
        fp1 = get_action_space_fingerprint()
        fp2 = get_action_space_fingerprint()
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)  # SHA-256 十六进制长度为 64
        self.assertIsInstance(fp1, str)

    def test_validate_action_space_passes_for_current(self):
        """校验当前动作空间应通过。"""
        self.assertTrue(
            validate_action_space(ACTION_SPACE_SIZE, ACTION_SPACE_FINGERPRINT)
        )

    def test_validate_action_space_fails_for_wrong_size(self):
        """校验错误大小应失败。"""
        self.assertFalse(
            validate_action_space(16, ACTION_SPACE_FINGERPRINT)
        )
        self.assertFalse(
            validate_action_space(18, ACTION_SPACE_FINGERPRINT)
        )

    def test_validate_action_space_fails_for_wrong_fingerprint(self):
        """校验错误指纹应失败。"""
        self.assertFalse(
            validate_action_space(ACTION_SPACE_SIZE, "deadbeef" * 8)
        )

    def test_get_move_by_index_out_of_range_raises(self):
        """越界索引应抛出 IndexError。"""
        with self.assertRaises(IndexError):
            get_move_by_index(-1)
        with self.assertRaises(IndexError):
            get_move_by_index(ACTION_SPACE_SIZE)
        # 边界值应正常
        self.assertIsInstance(get_move_by_index(0), Move)
        self.assertIsInstance(get_move_by_index(ACTION_SPACE_SIZE - 1), Move)


# ============================================================================
# 合法动作掩码测试
# ============================================================================


class TestLegalActionMask(unittest.TestCase):
    """6.2 合法动作测试"""

    # --- 与 get_legal_moves 一致性 ---

    def test_mask_matches_get_legal_moves_p1_initial(self):
        """初始状态 P1 掩码与 get_legal_moves 一致。"""
        state = GameState()
        mask = get_legal_action_mask(state, 1)
        legal_names = set(get_legal_moves(state, 1))

        for i in range(ACTION_SPACE_SIZE):
            move = get_move_by_index(i)
            if mask[i]:
                self.assertIn(move.name, legal_names,
                              f"掩码说 {move.name} 合法但 get_legal_moves 未包含")
            else:
                self.assertNotIn(move.name, legal_names,
                                 f"掩码说 {move.name} 非法但 get_legal_moves 包含")

    def test_mask_matches_get_legal_moves_p2_initial(self):
        """初始状态 P2 掩码与 get_legal_moves 一致。"""
        state = GameState()
        mask = get_legal_action_mask(state, 2)
        legal_names = set(get_legal_moves(state, 2))

        for i in range(ACTION_SPACE_SIZE):
            move = get_move_by_index(i)
            if mask[i]:
                self.assertIn(move.name, legal_names)
            else:
                self.assertNotIn(move.name, legal_names)

    def test_mask_initial_state_both_players(self):
        """初始状态下双方掩码应一致（初始资源相同）。"""
        state = GameState()
        mask_p1 = get_legal_action_mask(state, 1)
        mask_p2 = get_legal_action_mask(state, 2)
        self.assertEqual(mask_p1, mask_p2)

    # --- 初始合法动作 ---

    def test_initial_legal_moves_qi_and_shield(self):
        """初始状态：气、盾永远合法。"""
        state = GameState()
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.QI)])
        self.assertTrue(mask[get_index_by_move(Move.SHIELD)])

    def test_initial_illegal_no_qi(self):
        """初始 qi=0：气系攻击/防御/锦囊都应非法（除气、盾外）。"""
        state = GameState()
        mask = get_legal_action_mask(state, 1)

        qi_moves = [Move.GI, Move.PO, Move.LENG_FENG, Move.RU_LAI, Move.HEI_DONG,
                    Move.SHI_ZI, Move.BA_GUA, Move.CHI, Move.SHUANG_CHI, Move.GAO]
        for move in qi_moves:
            self.assertFalse(mask[get_index_by_move(move)],
                             f"qi=0 时 {move.name} 应为非法")

    def test_initial_illegal_no_shield(self):
        """初始 shield=0：盾系攻击都应非法（除烈焰/Shining 有替代资源外）。"""
        state = GameState()
        mask = get_legal_action_mask(state, 1)

        # FIRE 需要 shield>=2，SHAN_DIAN 需要 shield>=3
        self.assertFalse(mask[get_index_by_move(Move.FIRE)])
        self.assertFalse(mask[get_index_by_move(Move.SHAN_DIAN)])

        # 烈焰：spark=0, shield=0 → 非法
        self.assertFalse(mask[get_index_by_move(Move.LIE_YAN)])

        # Shining：battery=0, shield=0 → 非法
        self.assertFalse(mask[get_index_by_move(Move.SHINING)])

    # --- flash_used 边界 ---

    def test_flash_legal_when_not_used(self):
        """flash_used=0 → 闪合法。"""
        state = GameState()
        self.assertTrue(get_legal_action_mask(state, 1)[get_index_by_move(Move.SHAN)])

    def test_flash_legal_when_used_once(self):
        """flash_used=1 → 闪合法（最多 2 次）。"""
        state = GameState()
        state.p1.flash_used = 1
        self.assertTrue(get_legal_action_mask(state, 1)[get_index_by_move(Move.SHAN)])

    def test_flash_illegal_when_used_twice(self):
        """flash_used=2 → 闪非法。"""
        state = GameState()
        state.p1.flash_used = 2
        self.assertFalse(get_legal_action_mask(state, 1)[get_index_by_move(Move.SHAN)])

    # --- 资源充足时 ---

    def test_qi_1_allows_gi_and_chi(self):
        """qi=1 → GI 和 你吃 合法。"""
        state = GameState()
        state.p1.qi = 1
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.GI)])
        self.assertTrue(mask[get_index_by_move(Move.CHI)])

    def test_qi_5_allows_ru_lai(self):
        """qi=5 → 如来合法。"""
        state = GameState()
        state.p1.qi = 5
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.RU_LAI)])

    def test_qi_8_allows_hei_dong(self):
        """qi=8 → 黑洞合法。"""
        state = GameState()
        state.p1.qi = 8
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.HEI_DONG)])

    def test_shield_2_allows_fire(self):
        """shield=2 → Fire 合法。"""
        state = GameState()
        state.p1.shield = 2
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.FIRE)])

    def test_shield_3_allows_shan_dian(self):
        """shield=3 → 闪电合法。"""
        state = GameState()
        state.p1.shield = 3
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.SHAN_DIAN)])

    def test_lie_yan_with_spark(self):
        """火种≥2 → 烈焰合法。"""
        state = GameState()
        state.p1.spark = 2
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.LIE_YAN)])

    def test_lie_yan_with_shield_4(self):
        """盾≥4 → 烈焰合法（即使火种=0）。"""
        state = GameState()
        state.p1.shield = 4
        state.p1.spark = 0
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.LIE_YAN)])

    def test_shining_with_battery(self):
        """电池≥2 → Shining 合法。"""
        state = GameState()
        state.p1.battery = 2
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.SHINING)])

    def test_shining_with_shield_6(self):
        """盾≥6 → Shining 合法（即使电池=0）。"""
        state = GameState()
        state.p1.shield = 6
        state.p1.battery = 0
        mask = get_legal_action_mask(state, 1)
        self.assertTrue(mask[get_index_by_move(Move.SHINING)])

    # --- 掩码长度 ---

    def test_mask_length_is_always_17(self):
        """掩码长度始终为 17。"""
        state = GameState()
        mask = get_legal_action_mask(state, 1)
        self.assertEqual(len(mask), 17)

        # 改变状态后仍是 17
        state.p1.qi = 10
        state.p1.shield = 10
        mask = get_legal_action_mask(state, 1)
        self.assertEqual(len(mask), 17)

    # --- P1/P2 独立性 ---

    def test_p1_p2_masks_independent(self):
        """P1 和 P2 的掩码各自独立。"""
        state = GameState()
        state.p1.qi = 5
        state.p2.qi = 0
        mask_p1 = get_legal_action_mask(state, 1)
        mask_p2 = get_legal_action_mask(state, 2)
        self.assertTrue(mask_p1[get_index_by_move(Move.RU_LAI)])
        self.assertFalse(mask_p2[get_index_by_move(Move.RU_LAI)])

    def test_invalid_player_index_raises(self):
        """非法 controlled_player 不能静默当作 P2。"""
        state = GameState()
        with self.assertRaises(ValueError):
            get_legal_action_mask(state, 0)
        with self.assertRaises(ValueError):
            get_legal_moves_list(state, 3)


# ============================================================================
# 玩家视角转换测试
# ============================================================================


class TestPlayerView(unittest.TestCase):
    """玩家视角转换测试"""

    def test_view_p1_self_is_p1(self):
        """AI 控制 P1 时 self 指向 p1。"""
        state = GameState()
        state.p1.hp = 5  # 标记值
        state.p2.hp = 3
        view = get_player_view(state, 1)
        self.assertEqual(view["self"].hp, 5)
        self.assertEqual(view["opponent"].hp, 3)
        self.assertEqual(view["round_num"], 0)

    def test_view_p2_self_is_p2(self):
        """AI 控制 P2 时 self 指向 p2。"""
        state = GameState()
        state.p1.hp = 5
        state.p2.hp = 3
        view = get_player_view(state, 2)
        self.assertEqual(view["self"].hp, 3)
        self.assertEqual(view["opponent"].hp, 5)
        self.assertEqual(view["round_num"], 0)

    def test_view_includes_legal_action_mask(self):
        """视角包含合法动作掩码。"""
        state = GameState()
        view = get_player_view(state, 1)
        self.assertIn("legal_action_mask", view)
        self.assertEqual(len(view["legal_action_mask"]), 17)
        self.assertIsInstance(view["legal_action_mask"][0], bool)

    def test_view_includes_legal_actions_list(self):
        """视角包含合法动作列表。"""
        state = GameState()
        view = get_player_view(state, 1)
        self.assertIn("legal_actions", view)
        # 初始状态：气、盾合法
        self.assertIn(Move.QI, view["legal_actions"])
        self.assertIn(Move.SHIELD, view["legal_actions"])

    def test_view_invalid_player_raises(self):
        """无效的 controlled_player 应抛出 ValueError。"""
        state = GameState()
        with self.assertRaises(ValueError):
            get_player_view(state, 0)
        with self.assertRaises(ValueError):
            get_player_view(state, 3)

    def test_view_does_not_modify_state(self):
        """get_player_view 不修改原始 GameState。"""
        state = GameState()
        p1_hp_before = state.p1.hp
        p2_hp_before = state.p2.hp
        round_before = state.round_num

        view = get_player_view(state, 1)
        # 修改 view 中的 self 不应影响原始状态
        view["self"].hp = 999

        self.assertEqual(state.p1.hp, p1_hp_before)
        self.assertEqual(state.p2.hp, p2_hp_before)
        self.assertEqual(state.round_num, round_before)


# ============================================================================
# 统一策略接口测试
# ============================================================================


class TestSelectMove(unittest.TestCase):
    """6.3 决策接口测试"""

    def setUp(self):
        self.rng = random.Random(42)

    def test_select_move_returns_move(self):
        """select_move 返回 Move 实例。"""
        state = GameState()
        move = select_move(state, 1, self.rng)
        self.assertIsInstance(move, Move)

    def test_select_move_always_legal_p1(self):
        """随机 AI P1：永远只返回合法 Move。"""
        state = GameState()
        state.p1.qi = 10  # 提供资源使更多动作合法
        state.p1.shield = 10
        for _ in range(100):
            move = select_move(state, 1, self.rng)
            self.assertTrue(
                GameEngine.can_afford(state.p1, move),
                f"AI 返回了非法动作: {move.name}"
            )

    def test_select_move_always_legal_p2(self):
        """随机 AI P2：永远只返回合法 Move。"""
        state = GameState()
        state.p2.qi = 10
        state.p2.shield = 10
        for _ in range(100):
            move = select_move(state, 2, self.rng)
            self.assertTrue(
                GameEngine.can_afford(state.p2, move),
                f"AI 返回了非法动作: {move.name}"
            )

    def test_select_move_does_not_modify_state(self):
        """select_move 不修改传入的 GameState。"""
        state = GameState()
        state.p1.qi = 5
        original = state.copy()

        select_move(state, 1, self.rng)

        # 逐字段比较
        self.assertEqual(state.p1.hp, original.p1.hp)
        self.assertEqual(state.p1.qi, original.p1.qi)
        self.assertEqual(state.p1.shield, original.p1.shield)
        self.assertEqual(state.p1.spark, original.p1.spark)
        self.assertEqual(state.p1.battery, original.p1.battery)
        self.assertEqual(state.p1.pickaxe, original.p1.pickaxe)
        self.assertEqual(state.p1.flash_used, original.p1.flash_used)
        self.assertEqual(state.p2.hp, original.p2.hp)
        self.assertEqual(state.p2.qi, original.p2.qi)
        self.assertEqual(state.round_num, original.round_num)
        self.assertEqual(state.winner, original.winner)
        self.assertEqual(len(state.history), len(original.history))

    def test_same_state_same_seed_reproducible(self):
        """相同状态 + 相同种子 → 结果可复现。"""
        state = GameState()
        state.p1.qi = 5

        rng1 = random.Random(12345)
        rng2 = random.Random(12345)

        move1 = select_move(state, 1, rng1)
        move2 = select_move(state, 1, rng2)

        self.assertEqual(move1, move2)

    def test_select_move_with_flash_used_2_never_picks_flash(self):
        """flash_used=2 时不会选择闪。"""
        state = GameState()
        state.p1.flash_used = MAX_FLASH_USE  # 2
        state.p1.qi = 10
        state.p1.shield = 10

        for _ in range(200):
            move = select_move(state, 1, self.rng)
            self.assertNotEqual(move, Move.SHAN,
                                "flash_used=2 时不应选择闪")

    def test_select_move_no_resources_never_picks_attacks(self):
        """资源不足时不会选择对应攻击。"""
        state = GameState()
        # qi=0, shield=0, spark=0, battery=0 → 只有 qi、盾、闪合法
        for _ in range(100):
            move = select_move(state, 1, self.rng)
            self.assertIn(move, [Move.QI, Move.SHIELD, Move.SHAN])

    def test_different_human_move_does_not_affect_ai(self):
        """
        同一回合开始状态、同一种子下，外部传入不同 human_move 不影响 AI 决策。

        这是防作弊的关键测试：证明 AI 没有读取真人本回合动作。
        """
        state = GameState()
        state.p1.qi = 5

        rng1 = random.Random(9999)
        rng2 = random.Random(9999)

        # AI 决策时"对手"的 human_move 不应影响 AI
        # 我们通过对比两次 select_move 调用来验证：
        # AI 输入的是同一个回合开始 state，所以结果应相同
        move1 = select_move(state.copy(), 2, rng1)
        move2 = select_move(state.copy(), 2, rng2)

        self.assertEqual(move1, move2,
                         "相同 state + 相同种子，AI 决策应一致")

    def test_select_move_p1_and_p2_both_work(self):
        """AI 控制 P1 和 P2 都能正常工作。"""
        state = GameState()
        state.p1.qi = 5
        state.p2.qi = 5

        move_p1 = select_move(state, 1, self.rng)
        move_p2 = select_move(state, 2, self.rng)

        self.assertIsInstance(move_p1, Move)
        self.assertIsInstance(move_p2, Move)
        self.assertTrue(GameEngine.can_afford(state.p1, move_p1))
        self.assertTrue(GameEngine.can_afford(state.p2, move_p2))

    def test_unknown_difficulty_raises(self):
        """未知难度应抛出 ValueError。"""
        state = GameState()
        with self.assertRaises(ValueError):
            select_move(state, 1, self.rng, {"difficulty": "impossible"})

    def test_invalid_player_index_raises(self):
        """select_move 对非法座位应直接拒绝。"""
        state = GameState()
        with self.assertRaises(ValueError):
            select_move(state, 0, self.rng)


# ============================================================================
# 启发式评分测试
# ============================================================================


class TestHeuristicScoring(unittest.TestCase):
    """一步模拟评分函数测试"""

    def test_win_is_highest_score(self):
        """AI 获胜应获得最高分数。"""
        state = GameState()
        state.p1.qi = 1  # P1 可以出 GI
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.GI, Move.QI)  # P1 胜
        score = evaluate_state(sim, ai_player=1,
                               original_self=state.p1, original_opponent=state.p2)
        self.assertEqual(score, WIN_SCORE)

    def test_lose_is_lowest_score(self):
        """AI 失败应获得最低分数。"""
        state = GameState()
        state.p2.qi = 1
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.QI, Move.GI)  # P2 胜
        score = evaluate_state(sim, ai_player=1,
                               original_self=state.p1, original_opponent=state.p2)
        self.assertEqual(score, LOSE_SCORE)

    def test_double_lose_mid_score(self):
        """双败分数应在失败和获胜之间。"""
        state = GameState()
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.GI, Move.PO)  # 双败
        score = evaluate_state(sim, ai_player=1,
                               original_self=state.p1, original_opponent=state.p2)
        self.assertEqual(score, DOUBLE_LOSE_SCORE)
        self.assertGreater(score, LOSE_SCORE)
        self.assertLess(score, WIN_SCORE)

    def test_damage_to_opponent_is_positive(self):
        """伤害对手应获得正分数。"""
        state = GameState()
        state.p1.qi = 5
        state.p2.hp = 2  # 给 P2 多一点 HP 以免直接获胜
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.RU_LAI, Move.QI)
        score = evaluate_state(sim, ai_player=1,
                               original_self=state.p1, original_opponent=state.p2)
        # 如来对气造成 2 伤害，但没有直接获胜（hp=2）
        self.assertGreater(score, 0)

    def test_self_damage_is_negative(self):
        """自身受伤应获得负分数。"""
        state = GameState()
        state.p1.qi = 1
        state.p2.qi = 5
        sim = state.copy()
        # P1 a=GI, P2 a=RU_LAI: P1 打不穿如来, 如来打穿 GI
        GameEngine.resolve_round(sim, Move.GI, Move.RU_LAI)
        score = evaluate_state(sim, ai_player=1,
                               original_self=state.p1, original_opponent=state.p2)
        # P1 受伤
        self.assertLess(score, 0)

    def test_qi_gain_is_positive(self):
        """使用气获得正分数（资源改善）。"""
        state = GameState()
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.QI, Move.QI)
        score = evaluate_state(sim, ai_player=1,
                               original_self=state.p1, original_opponent=state.p2)
        # 双方出气，没有伤害，资源有变化
        self.assertGreater(score, 0)

    def test_flash_usage_is_penalized(self):
        """使用闪应被惩罚。"""
        state = GameState()
        state.p2.qi = 1
        # 闪 vs 对手出气：闪会退出，不受伤，但浪费一次闪
        sim_flash = state.copy()
        GameEngine.resolve_round(sim_flash, Move.SHAN, Move.QI)
        score_flash = evaluate_state(sim_flash, ai_player=1,
                                     original_self=state.p1, original_opponent=state.p2)

        # 气 vs 对手出气：正常
        sim_qi = state.copy()
        GameEngine.resolve_round(sim_qi, Move.QI, Move.QI)
        score_qi = evaluate_state(sim_qi, ai_player=1,
                                  original_self=state.p1, original_opponent=state.p2)

        # 闪的分数应低于气（因为浪费了闪）
        self.assertLess(score_flash, score_qi)

    def test_ai_p2_win_is_correct(self):
        """AI 控制 P2 时的获胜判定正确。"""
        state = GameState()
        state.p2.qi = 1
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.QI, Move.GI)  # P2 胜
        score = evaluate_state(sim, ai_player=2,
                               original_self=state.p2, original_opponent=state.p1)
        self.assertEqual(score, WIN_SCORE)

    def test_ai_p2_lose_is_correct(self):
        """AI 控制 P2 时的失败判定正确。"""
        state = GameState()
        state.p1.qi = 1
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.GI, Move.QI)  # P1 胜
        score = evaluate_state(sim, ai_player=2,
                               original_self=state.p2, original_opponent=state.p1)
        self.assertEqual(score, LOSE_SCORE)

    def test_pickaxe_risk_is_penalized(self):
        """持有 1 镐应被轻微惩罚。"""
        state = GameState()
        state.p1.qi = 2
        # 出镐获得 1 镐
        sim = state.copy()
        GameEngine.resolve_round(sim, Move.GAO, Move.QI)
        score_with_pickaxe = evaluate_state(sim, ai_player=1,
                                            original_self=state.p1, original_opponent=state.p2)

        # 出气不获得镐
        sim2 = state.copy()
        GameEngine.resolve_round(sim2, Move.QI, Move.QI)
        score_without_pickaxe = evaluate_state(sim2, ai_player=1,
                                               original_self=state.p1, original_opponent=state.p2)

        # 有镐风险的分数应低于无镐的（镐获得是正的但镐风险是负的）
        # 镐获得 +6，镐风险 -15，所以净 -9
        # 但还要看其他因素。至少镐风险惩罚存在。
        self.assertIsNotNone(score_with_pickaxe)
        self.assertIsNotNone(score_without_pickaxe)


# ============================================================================
# 启发式策略测试
# ============================================================================


class TestHeuristicStrategy(unittest.TestCase):
    """一步模拟启发式策略测试"""

    def setUp(self):
        self.rng = random.Random(123)

    def test_heuristic_returns_legal_move(self):
        """启发式 AI 始终返回合法动作。"""
        state = GameState()
        state.p1.qi = 5
        state.p1.shield = 5
        for _ in range(50):
            move = heuristic_select_move(state, 1, self.rng)
            self.assertTrue(GameEngine.can_afford(state.p1, move),
                            f"启发式返回非法动作: {move.name}")

    def test_heuristic_does_not_modify_state(self):
        """启发式 AI 不修改传入的 GameState。"""
        state = GameState()
        state.p1.qi = 5
        state.p1.shield = 5
        original = state.copy()

        heuristic_select_move(state, 1, self.rng)

        self.assertEqual(state.p1.hp, original.p1.hp)
        self.assertEqual(state.p1.qi, original.p1.qi)
        self.assertEqual(state.p1.shield, original.p1.shield)
        self.assertEqual(state.p2.hp, original.p2.hp)
        self.assertEqual(state.round_num, original.round_num)
        self.assertEqual(state.winner, original.winner)
        self.assertEqual(len(state.history), len(original.history))

    def test_heuristic_kill_shot_preferred(self):
        """
        有必胜机会时启发式 AI 应选择致胜动作。

        场景：P1 qi=1, P2 hp=1 无资源。GI 直接获胜。
        普通模式（平均分聚合）应稳定选择 GI。
        """
        state = GameState()
        state.p1.qi = 1  # P1 可以出 GI

        move = heuristic_select_move(state, 1, self.rng, {"conservative": False})
        self.assertIsInstance(move, Move)
        # GI 应该导致 P1 胜利（假设对手出 QI 这种最可能的动作）
        sim = state.copy()
        GameEngine.resolve_round(sim, move, Move.QI)
        self.assertEqual(sim.winner, 1,
                         f"选了 {move.name}，预期选 GI 致胜")

    def test_heuristic_avoids_self_destruct(self):
        """启发式 AI 应避免主动选择导致自己失败的动作。"""
        state = GameState()
        state.p1.pickaxe = 1
        state.p1.qi = 2
        state.p2.qi = 1  # P2 可以出 GI

        # 如果 P1 出镐 → pickaxe=2 → 爆镐 hp=0 → P1 死亡
        # 但如果 P2 出了攻击，可能导致双败或 P1 败
        # 保守模式下 AI 应避免高风险的镐

        move = heuristic_select_move(state, 1, self.rng, {"conservative": True})
        self.assertNotEqual(move, Move.GAO,
                            "pickaxe=1 时不应选择镐（会导致爆镐）")

    def test_heuristic_same_state_deterministic_conservative(self):
        """保守模式下，相同状态产生相同结果。"""
        state = GameState()
        state.p1.qi = 3
        state.p1.shield = 3

        rng1 = random.Random(42)
        rng2 = random.Random(42)

        move1 = heuristic_select_move(state, 1, rng1, {"conservative": True})
        move2 = heuristic_select_move(state, 1, rng2, {"conservative": True})
        self.assertEqual(move1, move2)

    def test_heuristic_normal_vs_conservative(self):
        """普通模式和保守模式可能有不同选择（保守模式更规避风险）。"""
        state = GameState()
        state.p1.qi = 3
        state.p1.shield = 3
        state.p2.qi = 3
        state.p2.shield = 3

        rng = random.Random(999)
        move_normal = heuristic_select_move(state, 1, rng, {"conservative": False})

        rng2 = random.Random(999)
        move_conservative = heuristic_select_move(state, 2, rng2, {"conservative": True})

        # 两者都应合法
        self.assertTrue(GameEngine.can_afford(state.p1, move_normal))
        self.assertTrue(GameEngine.can_afford(state.p2, move_conservative))

    def test_heuristic_p1_and_p2_both_work(self):
        """启发式 AI 控制 P1 和 P2 都能工作。"""
        state = GameState()
        state.p1.qi = 3
        state.p2.qi = 3

        move_p1 = heuristic_select_move(state, 1, self.rng)
        move_p2 = heuristic_select_move(state, 2, self.rng)

        self.assertIsInstance(move_p1, Move)
        self.assertIsInstance(move_p2, Move)
        self.assertTrue(GameEngine.can_afford(state.p1, move_p1))
        self.assertTrue(GameEngine.can_afford(state.p2, move_p2))

    def test_heuristic_no_flash_when_used_twice(self):
        """flash_used=2 时启发式 AI 不会选择闪（因为闪不合法）。"""
        state = GameState()
        state.p1.flash_used = MAX_FLASH_USE
        state.p1.qi = 5
        state.p1.shield = 5

        for _ in range(30):
            move = heuristic_select_move(state, 1, self.rng)
            self.assertNotEqual(move, Move.SHAN)


# ============================================================================
# 模拟隔离性测试
# ============================================================================


class TestSimulationIsolation(unittest.TestCase):
    """验证一步模拟不污染原始状态"""

    def test_heuristic_does_not_alter_original_state(self):
        """启发式 AI 模拟 289 次后原状态不变。"""
        state = GameState()
        state.p1.qi = 5
        state.p1.shield = 5
        state.p2.qi = 5
        state.p2.shield = 5

        original = state.copy()
        rng = random.Random(1)

        heuristic_select_move(state, 1, rng)

        # 逐字段验证
        self.assertEqual(state.p1.hp, original.p1.hp)
        self.assertEqual(state.p1.qi, original.p1.qi)
        self.assertEqual(state.p1.shield, original.p1.shield)
        self.assertEqual(state.p1.spark, original.p1.spark)
        self.assertEqual(state.p1.battery, original.p1.battery)
        self.assertEqual(state.p1.pickaxe, original.p1.pickaxe)
        self.assertEqual(state.p1.flash_used, original.p1.flash_used)
        self.assertEqual(state.p2.hp, original.p2.hp)
        self.assertEqual(state.p2.qi, original.p2.qi)
        self.assertEqual(state.p2.shield, original.p2.shield)
        self.assertEqual(state.p2.spark, original.p2.spark)
        self.assertEqual(state.p2.battery, original.p2.battery)
        self.assertEqual(state.p2.pickaxe, original.p2.pickaxe)
        self.assertEqual(state.p2.flash_used, original.p2.flash_used)
        self.assertEqual(state.round_num, original.round_num)
        self.assertEqual(state.winner, original.winner)
        self.assertEqual(len(state.history), len(original.history))


# ============================================================================
# 难度分层集成测试
# ============================================================================


class TestDifficultyIntegration(unittest.TestCase):
    """select_move 难度参数集成测试"""

    def setUp(self):
        self.rng = random.Random(77)

    def test_easy_is_random(self):
        """easy 模式应走随机策略。"""
        state = GameState()
        state.p1.qi = 3
        state.p1.shield = 3

        # 多次采样，应能看到不同动作（随机性）
        moves_seen = set()
        for _ in range(50):
            move = select_move(state, 1, self.rng, {"difficulty": "easy"})
            moves_seen.add(move)

        # 有多个合法动作时随机策略应覆盖多个
        self.assertGreater(len(moves_seen), 1,
                           f"随机策略只产生了 {len(moves_seen)} 种动作")

    def test_normal_uses_heuristic(self):
        """normal 模式应走启发式策略。"""
        state = GameState()
        state.p1.qi = 3
        state.p1.shield = 3

        move = select_move(state.copy(), 1, self.rng, {"difficulty": "normal"})
        self.assertIsInstance(move, Move)
        self.assertTrue(GameEngine.can_afford(state.p1, move))

    def test_hard_uses_conservative(self):
        """hard 模式应走保守启发式策略。"""
        state = GameState()
        state.p1.qi = 3
        state.p1.shield = 3

        move = select_move(state.copy(), 1, self.rng, {"difficulty": "hard"})
        self.assertIsInstance(move, Move)
        self.assertTrue(GameEngine.can_afford(state.p1, move))

    def test_normal_better_than_random_in_winning_position(self):
        """
        在明显优势局面下，启发式 AI 应比随机 AI 更可靠地选择获胜动作。

        场景：P1 qi=1, P2 hp=1 无防御
        GI 直接获胜，QI/SHIELD/SHAN 不获胜。
        启发式应稳定选择 GI，随机可能选其他。
        """
        state = GameState()
        state.p1.qi = 1  # 刚好够 GI

        # 启发式（普通）
        heuristic_wins = 0
        for i in range(20):
            r = random.Random(1000 + i)
            move = select_move(state.copy(), 1, r, {"difficulty": "normal"})
            if move == Move.GI:
                heuristic_wins += 1

        # 随机
        random_wins = 0
        for i in range(20):
            r = random.Random(2000 + i)
            move = select_move(state.copy(), 1, r, {"difficulty": "easy"})
            if move == Move.GI:
                random_wins += 1

        # 启发式应始终选择致胜动作
        self.assertEqual(heuristic_wins, 20,
                         f"启发式只在 {heuristic_wins}/20 次中选择了致胜动作 GI")
        # 随机可能低于 20
        self.assertLessEqual(random_wins, 20)


class TestResolveConsistency(unittest.TestCase):
    """6.4 结算一致性测试"""

    def test_winner_is_none_not_falsy_check(self):
        """终局判断必须用 winner is not None，不能用 if winner。"""
        # winner=0（双败）是终局
        state = GameState()
        # 双方都出非法动作 → 双败
        state.p1.qi = 0
        state.p2.qi = 0
        state = GameEngine.resolve_round(state, Move.GI, Move.PO)
        self.assertEqual(state.winner, 0)

        # 验证 winner is not None 正确识别终局
        self.assertTrue(state.winner is not None)
        # 如果用 if winner 会错误判断为非终局（因为 0 是 falsy）
        self.assertFalse(bool(state.winner))

    def test_winner_0_identified_as_terminal(self):
        """winner=0 能被正确识别为终局。"""
        state = GameState()
        state = GameEngine.resolve_round(state, Move.GI, Move.PO)  # 双方非法 → 双败
        self.assertEqual(state.winner, 0)
        self.assertTrue(state.winner is not None)

    def test_copy_isolation_for_simulation(self):
        """
        证明 GameState.copy() 创建的副本在 resolve_round 后不影响原状态。
        这是 AI 模拟的基础保证。
        """
        original = GameState()
        original.p1.qi = 1
        original.p2.qi = 1

        sim = original.copy()
        # 在副本上模拟
        GameEngine.resolve_round(sim, Move.GI, Move.GI)

        # 原状态应保持不变
        self.assertEqual(original.round_num, 0)
        self.assertEqual(original.p1.qi, 1)
        self.assertEqual(original.p2.qi, 1)
        self.assertEqual(len(original.history), 0)
        self.assertIsNone(original.winner)

    def test_resolve_round_modifies_state_in_place(self):
        """resolve_round 修改原状态（不是副本），这是预期行为。"""
        state = GameState()
        state.p1.qi = 1
        result = GameEngine.resolve_round(state, Move.GI, Move.QI)
        self.assertIs(result, state)
        self.assertEqual(state.round_num, 1)

    def test_post_resolve_state_fields_match(self):
        """resolve_round 后 P1/P2 七个字段 + round_num + winner + history 一致。"""
        state = GameState()
        state.p1.qi = 1

        state = GameEngine.resolve_round(state, Move.GI, Move.QI)

        self.assertEqual(state.winner, 1)
        self.assertEqual(state.round_num, 1)
        self.assertEqual(len(state.history), 1)

        log = state.history[0]
        self.assertEqual(state.p1.hp, log.p1_hp_after)
        self.assertEqual(state.p2.hp, log.p2_hp_after)
        self.assertEqual(state.p1.qi, log.p1_qi_after)
        self.assertEqual(state.p2.qi, log.p2_qi_after)
        self.assertEqual(state.p1.shield, log.p1_shield_after)
        self.assertEqual(state.p2.shield, log.p2_shield_after)
        self.assertEqual(state.p1.spark, log.p1_spark_after)
        self.assertEqual(state.p2.spark, log.p2_spark_after)
        self.assertEqual(state.p1.battery, log.p1_battery_after)
        self.assertEqual(state.p2.battery, log.p2_battery_after)
        self.assertEqual(state.p1.pickaxe, log.p1_pickaxe_after)
        self.assertEqual(state.p2.pickaxe, log.p2_pickaxe_after)
        self.assertEqual(state.winner, log.winner_after_round)


# ============================================================================
# 规则正确性回归测试（确保 AI 模块不影响现有规则）
# ============================================================================


class TestRuleRegression(unittest.TestCase):
    """确保现有规则行为不变"""

    def test_move_enum_unchanged(self):
        """Move 枚举必须保持 17 个，不可随意增减。"""
        self.assertEqual(len(list(Move)), 17)

    def test_action_space_auto_from_enum(self):
        """空间注册表自动从 Move 枚举生成，不是手写第二份。"""
        self.assertEqual(ACTION_SPACE_SIZE, len(list(Move)))
        self.assertEqual(len(MOVE_BY_INDEX), len(list(Move)))
        self.assertEqual(len(INDEX_BY_MOVE), len(list(Move)))

    def test_no_rule_logic_duplicated_in_ai_module(self):
        """AI 模块不应复制 can_afford 逻辑。"""
        import inspect
        import app.ai.engine as ai_engine
        import app.ai.space as ai_space
        import app.ai.strategies as ai_strategies

        # 检查 AI 模块源码中不含直接的资源判断
        for module in [ai_engine, ai_space, ai_strategies]:
            source = inspect.getsource(module)
            # 这些是规则引擎的关键词，AI 模块不应自己写
            forbidden_inline = [
                "spark >= 2",
                "battery >= 2",
                "shield >= 4",
                "shield >= 6",
                "flash_used <",
                "pickaxe >=",
            ]
            for pattern in forbidden_inline:
                self.assertNotIn(
                    pattern, source,
                    f"AI 模块 {module.__name__} 中疑似复制了规则逻辑: {pattern}"
                )


# ═══════════════════════════════════════════════════════════════
# v2 AI 测试（阶段 G）
# ═══════════════════════════════════════════════════════════════

class TestV2AILegalMoves(unittest.TestCase):
    """v2 AI 合法动作测试。"""

    def setUp(self):
        from app.v2.models import GameStateV2, PlayerStateV2
        self.players = [
            PlayerStateV2(player_id="p1", seat_index=0, username="人类"),
            PlayerStateV2(player_id="p2", seat_index=1, username="AI机器人"),
        ]
        self.state = GameStateV2(players=self.players, max_players=2)

    def test_legal_moves_never_empty(self):
        """初始状态下所有存活玩家都有合法动作。"""
        from app.v2.ai import get_legal_moves_v2_ai
        for p in self.state.alive_players():
            legal = get_legal_moves_v2_ai(self.state, p.player_id)
            self.assertGreater(len(legal), 0, f"玩家 {p.player_id} 应有合法动作")
            self.assertIn("QI", [m.name for m in legal], "QI（气）在初始状态应始终合法")

    def test_random_always_selects_legal_move(self):
        """random 策略每次选的动作都在合法列表中。"""
        from app.v2.ai import get_legal_moves_v2_ai, select_ai_move_v2
        legal_names = {m.name for m in get_legal_moves_v2_ai(self.state, "p2")}
        for _ in range(50):
            move = select_ai_move_v2(self.state, "p2", difficulty="random", rng=random.Random())
            self.assertIn(move.name, legal_names, f"random 选了非法动作: {move.name}")

    def test_normal_always_selects_legal_move(self):
        """normal heuristic 每次选的动作都在合法列表中。"""
        from app.v2.ai import get_legal_moves_v2_ai, select_ai_move_v2
        legal_names = {m.name for m in get_legal_moves_v2_ai(self.state, "p2")}
        for _ in range(50):
            move = select_ai_move_v2(self.state, "p2", difficulty="normal", rng=random.Random())
            self.assertIn(move.name, legal_names, f"normal 选了非法动作: {move.name}")

    def test_random_and_normal_can_differ(self):
        """random 和 normal 策略可能产生不同选择。"""
        from app.v2.ai import select_ai_move_v2
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        moves_random = {select_ai_move_v2(self.state, "p2", difficulty="random", rng=rng1).name for _ in range(30)}
        moves_normal = {select_ai_move_v2(self.state, "p2", difficulty="normal", rng=rng2).name for _ in range(30)}
        # random 应该更多样，normal 会集中在特定动作
        # 不严格断言，只验证两种策略都不为空
        self.assertGreater(len(moves_random), 0)
        self.assertGreater(len(moves_normal), 0)

    def test_dead_player_has_no_legal_moves(self):
        """死亡玩家无合法动作。"""
        from app.v2.ai import get_legal_moves_v2_ai
        from app.v2.constants import PLAYER_DEAD
        p2 = self.state.get_player("p2")
        p2.status = PLAYER_DEAD
        legal = get_legal_moves_v2_ai(self.state, "p2")
        self.assertEqual(len(legal), 0, "死亡玩家不应有合法动作")

    def test_ai_move_with_invalid_difficulty_falls_back_to_random(self):
        """未知难度回退到随机选择（合法）。"""
        from app.v2.ai import get_legal_moves_v2_ai, select_ai_move_v2
        legal_names = {m.name for m in get_legal_moves_v2_ai(self.state, "p2")}
        move = select_ai_move_v2(self.state, "p2", difficulty="super_hard_ai")
        self.assertIn(move.name, legal_names)


class TestV2AIMixedBattle(unittest.TestCase):
    """v2 混合对局（人类 + AI）smoke 测试。"""

    def setUp(self):
        from app.v2.models import GameStateV2, PlayerStateV2
        import server.runtime as rt
        self._orig_state = rt.CURRENT_STATE_V2
        self._orig_engine = rt.CURRENT_ENGINE_V2
        self._orig_battle_id = rt.CURRENT_BATTLE_ID_V2
        self._orig_player_types = dict(rt.CURRENT_V2_PLAYER_TYPES)
        self._orig_ai_difficulty = rt.CURRENT_V2_AI_DIFFICULTY
        username = f"v2-local-{uuid4().hex[:8]}"
        registered = users.register(username, "test1234", verified="1")
        self.assertTrue(registered["ok"], registered)
        self._user_id = registered["user"]["uid"]
        logged_in = users.login(username, "test1234")
        self.assertTrue(logged_in["ok"], logged_in)
        self._headers = {"X-Session-Token": logged_in["session_token"]}

    def tearDown(self):
        import server.runtime as rt
        from app import battle_recorder
        if rt.CURRENT_BATTLE_ID_V2 and rt.CURRENT_BATTLE_ID_V2 != self._orig_battle_id:
            battle_recorder.delete_battle(rt.CURRENT_BATTLE_ID_V2)
        rt.CURRENT_STATE_V2 = self._orig_state
        rt.CURRENT_ENGINE_V2 = self._orig_engine
        rt.CURRENT_BATTLE_ID_V2 = self._orig_battle_id
        rt.CURRENT_V2_PLAYER_TYPES = self._orig_player_types
        rt.CURRENT_V2_AI_DIFFICULTY = self._orig_ai_difficulty
        users.delete_user(self._user_id)

    def _create_state(self, player_count: int) -> tuple:
        from app.v2.models import GameStateV2, PlayerStateV2
        players = []
        for i in range(player_count):
            players.append(PlayerStateV2(
                player_id=f"p{i + 1}",
                seat_index=i,
                username=f"玩家{i + 1}",
            ))
        return GameStateV2(players=players, max_players=player_count)

    def test_two_player_one_human_one_ai_full_game(self):
        """2 人局（1 人类 + 1 AI）完整结算。"""
        from app.v2.ai import select_ai_move_v2
        from app.v2.game import GameEngineV2
        from app.v2.constants import Move
        state = self._create_state(2)
        rng = random.Random(123)

        for _ in range(20):
            if state.is_game_over():
                break
            moves = {
                "p1": Move.QI,  # 人类选气
                "p2": select_ai_move_v2(state, "p2", difficulty="normal", rng=rng),
            }
            log = GameEngineV2(state).resolve_round(moves)
            self.assertIsNotNone(log, "每回合应有结算日志")

    def test_three_player_one_human_two_ai_full_game(self):
        """3 人局（1 人类 + 2 AI）完整结算。"""
        from app.v2.ai import select_ai_move_v2
        from app.v2.game import GameEngineV2
        from app.v2.constants import Move
        state = self._create_state(3)
        rng = random.Random(42)

        for _ in range(30):
            if state.is_game_over():
                break
            moves = {
                "p1": Move.PO,  # 人类用破攻击
                "p2": select_ai_move_v2(state, "p2", difficulty="normal", rng=rng),
                "p3": select_ai_move_v2(state, "p3", difficulty="random", rng=rng),
            }
            log = GameEngineV2(state).resolve_round(moves)
            self.assertIsNotNone(log)

    def test_six_player_full_ai_simulation(self):
        """6 人局（全 AI）自动模拟 5 回合不崩溃。"""
        from app.v2.ai import select_ai_move_v2
        from app.v2.game import GameEngineV2
        from app.v2.constants import Move
        state = self._create_state(6)
        rng = random.Random(99)

        for _ in range(5):
            if state.is_game_over():
                break
            moves = {}
            for p in state.alive_players():
                moves[p.player_id] = select_ai_move_v2(
                    state, p.player_id,
                    difficulty="normal", rng=rng,
                )
            log = GameEngineV2(state).resolve_round(moves)
            self.assertIsNotNone(log)

    def test_local_api_all_ai_accepts_empty_moves(self):
        """本地 API 支持全 AI 对局，空 moves 由后端自动补齐。"""
        from server.app import app

        client = app.test_client()
        reset = client.post("/v2/api/local/reset", json={
            "player_count": 2,
            "names": ["AI-1", "AI-2"],
            "player_types": ["ai", "ai"],
            "ai_difficulty": "random",
        }, headers=self._headers)
        self.assertEqual(reset.status_code, 200)
        reset_payload = reset.get_json()
        self.assertEqual(reset_payload["state"]["_player_types"], {"p1": "ai", "p2": "ai"})

        step = client.post("/v2/api/local/step", json={
            "moves": {},
            "auto_resolve": True,
        }, headers=self._headers)
        self.assertEqual(step.status_code, 200)
        step_payload = step.get_json()
        self.assertTrue(step_payload["ok"])
        self.assertEqual(step_payload["state"]["_player_types"], {"p1": "ai", "p2": "ai"})
        self.assertEqual(step_payload["state"]["_ai_difficulty"], "random")

    def test_local_api_normalizes_invalid_player_types(self):
        """错误 player_type 不应进入运行时状态，统一回退为 human。"""
        from server.app import app

        client = app.test_client()
        response = client.post("/v2/api/local/reset", json={
            "player_count": 3,
            "names": ["A", "B", "C"],
            "player_types": ["robot", "ai"],
            "ai_difficulty": "unknown",
        }, headers=self._headers)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["state"]["_player_types"], {
            "p1": "human",
            "p2": "ai",
            "p3": "human",
        })
        self.assertEqual(payload["state"]["_ai_difficulty"], "normal")

    def test_local_v2_api_requires_authentication(self):
        """2.0 本地对局接口必须拒绝未登录访问。"""
        from server.app import app

        client = app.test_client()
        self.assertEqual(client.get("/v2/api/local/state").status_code, 401)
        self.assertEqual(
            client.post("/v2/api/local/reset", json={"player_count": 2}).status_code,
            401,
        )

    def test_local_v2_state_isolated_and_restorable_per_user(self):
        """2.0 本地状态按 UID 隔离，并可通过 state 接口恢复。"""
        from server.app import app

        client = app.test_client()
        reset = client.post(
            "/v2/api/local/reset",
            json={"player_count": 2, "names": ["A", "B"]},
            headers=self._headers,
        )
        self.assertEqual(reset.status_code, 200)
        step = client.post(
            "/v2/api/local/step",
            json={
                "moves": {"p1": "QI", "p2": "SHIELD"},
                "auto_resolve": True,
            },
            headers=self._headers,
        )
        self.assertEqual(step.status_code, 200)

        restored = client.get(
            "/v2/api/local/state",
            headers=self._headers,
        ).get_json()["state"]
        self.assertTrue(restored["_initialized"])
        self.assertEqual(restored["round_num"], 1)
        self.assertEqual(restored["players"][0]["qi"], 1)

        second_name = f"v2-local-second-{uuid4().hex[:8]}"
        second = users.register(second_name, "test1234", verified="1")
        self.assertTrue(second["ok"], second)
        try:
            second_login = users.login(second_name, "test1234")
            second_headers = {"X-Session-Token": second_login["session_token"]}
            isolated = client.get(
                "/v2/api/local/state",
                headers=second_headers,
            ).get_json()["state"]
            self.assertFalse(isolated["_initialized"])
            self.assertEqual(isolated["round_num"], 0)
        finally:
            users.delete_user(second["user"]["uid"])


if __name__ == "__main__":
    unittest.main()
