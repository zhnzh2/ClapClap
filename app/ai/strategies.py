"""
ClapClap 1.0 AI 一步模拟启发式策略。

核心逻辑：
  1. 获取 AI 合法动作集合 A
  2. 获取对手合法动作集合 B
  3. 对每个 (ai_move, opponent_move) 组合：
     - 复制 GameState
     - 调用 resolve_round() 模拟结算
     - 用模拟后的真实结果评分
  4. 聚合每个 ai_move 的分数（平均分 或 最差分）
  5. 选择评分最高的动作

评分完全通过 resolve_round() 得到，不重新实现规则。
每个模拟分支使用独立复制的 GameState，防止污染真实对局。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from app.v1.constants import Move
from app.v1.game import GameEngine
from app.v1.models import GameState, PlayerState
from app.ai.engine import get_legal_moves_list


# ---------------------------------------------------------------------------
# 评分常量
# ---------------------------------------------------------------------------

# 终局分数（绝对值最大，主导所有其他因素）
WIN_SCORE = 10_000
LOSE_SCORE = -10_000
DOUBLE_LOSE_SCORE = -5_000

# HP 变化分数
HP_DAMAGE_TO_OPPONENT_PER_POINT = 100
HP_LOST_PER_POINT = -120  # 自身掉血惩罚略高于对敌伤害，鼓励保守

# 自身资源变化分数
QI_GAIN_PER_POINT = 3
SHIELD_GAIN_PER_POINT = 4
SPARK_GAIN_PER_POINT = 3
BATTERY_GAIN_PER_POINT = 3
PICKAXE_GAIN_PER_POINT = 6

# 对手资源变化分数（对手变强对我们不利，所以取负）
OPP_QI_GAIN_PER_POINT = -2
OPP_SHIELD_GAIN_PER_POINT = -3
OPP_SPARK_GAIN_PER_POINT = -2
OPP_BATTERY_GAIN_PER_POINT = -2
OPP_PICKAXE_GAIN_PER_POINT = -4

# 特殊惩罚
FLASH_USED_PENALTY = -25       # 使用闪的代价
PICKAXE_AT_ONE_RISK = -15      # 持有 1 镐有爆镐风险


# ---------------------------------------------------------------------------
# 评分函数
# ---------------------------------------------------------------------------


def evaluate_state(
    simulated: GameState,
    ai_player: int,
    original_self: PlayerState,
    original_opponent: PlayerState,
) -> float:
    """
    从 AI 视角评估模拟后的 GameState。

    参数:
        simulated: resolve_round 后的状态。
        ai_player: 1 或 2，AI 控制的座位。
        original_self: 回合开始前 AI 的状态。
        original_opponent: 回合开始前对手的状态。

    返回:
        float: 分数，越高越好。
    """
    score = 0.0

    # 确定模拟后的 self 和 opponent
    if ai_player == 1:
        self_state = simulated.p1
        opp_state = simulated.p2
    else:
        self_state = simulated.p2
        opp_state = simulated.p1

    winner = simulated.winner

    # ---- 优先级 1-3: 终局判定 ----
    if winner is not None:
        if winner == 0:
            # 双败
            score += DOUBLE_LOSE_SCORE
        elif (ai_player == 1 and winner == 1) or (ai_player == 2 and winner == 2):
            # AI 获胜
            score += WIN_SCORE
        else:
            # AI 失败
            score += LOSE_SCORE
        # 终局时不再评估 HP 和资源（游戏已结束）
        return score

    # ---- 优先级 4: 降低对手生命 ----
    opp_hp_lost = original_opponent.hp - opp_state.hp
    if opp_hp_lost > 0:
        score += opp_hp_lost * HP_DAMAGE_TO_OPPONENT_PER_POINT

    # ---- 优先级 5: 保持自身生命 ----
    self_hp_lost = original_self.hp - self_state.hp
    if self_hp_lost > 0:
        score += self_hp_lost * HP_LOST_PER_POINT

    # ---- 优先级 6: 改善资源状态 ----
    # 自身资源
    score += (self_state.qi - original_self.qi) * QI_GAIN_PER_POINT
    score += (self_state.shield - original_self.shield) * SHIELD_GAIN_PER_POINT
    score += (self_state.spark - original_self.spark) * SPARK_GAIN_PER_POINT
    score += (self_state.battery - original_self.battery) * BATTERY_GAIN_PER_POINT
    score += (self_state.pickaxe - original_self.pickaxe) * PICKAXE_GAIN_PER_POINT

    # 对手资源
    score += (opp_state.qi - original_opponent.qi) * OPP_QI_GAIN_PER_POINT
    score += (opp_state.shield - original_opponent.shield) * OPP_SHIELD_GAIN_PER_POINT
    score += (opp_state.spark - original_opponent.spark) * OPP_SPARK_GAIN_PER_POINT
    score += (opp_state.battery - original_opponent.battery) * OPP_BATTERY_GAIN_PER_POINT
    score += (opp_state.pickaxe - original_opponent.pickaxe) * OPP_PICKAXE_GAIN_PER_POINT

    # ---- 优先级 7: 避免无意义消耗闪 ----
    if self_state.flash_used > original_self.flash_used:
        score += FLASH_USED_PENALTY

    # ---- 优先级 8: 避免爆镐高风险 ----
    # 注意：爆镐（pickaxe 达到 2）已被 winner 判定覆盖（爆镐 → hp=0 → 终局）
    # 这里只惩罚 pickaxe 为 1 的风险状态
    if self_state.pickaxe == 1:
        score += PICKAXE_AT_ONE_RISK

    return score


# ---------------------------------------------------------------------------
# 一步模拟
# ---------------------------------------------------------------------------


def _simulate_one(
    state: GameState,
    ai_move: Move,
    opp_move: Move,
    ai_player: int,
    original_self: PlayerState,
    original_opponent: PlayerState,
) -> float:
    """
    模拟一个 (ai_move, opp_move) 组合，返回分数。

    内部复制 GameState，不修改原始状态。
    """
    sim = state.copy()

    # 根据 AI 座位组装 p1_move / p2_move
    if ai_player == 1:
        p1_move = ai_move
        p2_move = opp_move
    else:
        p1_move = opp_move
        p2_move = ai_move

    GameEngine.resolve_round(sim, p1_move, p2_move)
    return evaluate_state(sim, ai_player, original_self, original_opponent)


def _aggregate_scores(
    scores: List[float],
    conservative: bool,
) -> float:
    """
    聚合对手各动作的分数。

    conservative=False: 平均分（普通难度）。
    conservative=True: 最差分（困难难度，假设对手最优应对）。
    """
    if not scores:
        return float("-inf")
    if conservative:
        return min(scores)
    else:
        return sum(scores) / len(scores)


def heuristic_select_move(
    state: GameState,
    controlled_player: int,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> Move:
    """
    一步模拟启发式 AI 策略。

    参数:
        state: 回合开始时的 GameState（不会被修改）。
        controlled_player: AI 控制的座位。
        rng: 随机数生成器。
        config: 可选配置。支持的键:
            - conservative: bool，默认 False。
              True → 最差分聚合（困难模式）。
              False → 平均分聚合 + 小概率随机探索（普通模式）。

    返回:
        Move: 评分最高的动作。
    """
    config = config or {}
    conservative = config.get("conservative", False)

    # 双方合法动作
    ai_legal = get_legal_moves_list(state, controlled_player)
    opp_player = 2 if controlled_player == 1 else 1
    opp_legal = get_legal_moves_list(state, opp_player)

    if not ai_legal:
        raise ValueError(f"AI (P{controlled_player}) 无合法动作可选")

    # 回合开始时的快照，用于评分比较
    if controlled_player == 1:
        original_self = state.p1
        original_opponent = state.p2
    else:
        original_self = state.p2
        original_opponent = state.p1

    # 对每个 AI 动作，遍历全部对手动作模拟评分
    move_scores: List[Tuple[Move, float]] = []

    for ai_move in ai_legal:
        scores: List[float] = []
        for opp_move in opp_legal:
            s = _simulate_one(
                state, ai_move, opp_move,
                controlled_player,
                original_self, original_opponent,
            )
            scores.append(s)

        aggregate = _aggregate_scores(scores, conservative)
        move_scores.append((ai_move, aggregate))

    # 按分数降序排序
    move_scores.sort(key=lambda x: x[1], reverse=True)
    best_score = move_scores[0][1]

    # 普通模式：在接近最优的动作中随机选择，增加变化性
    if not conservative:
        # 选前 N 个分数相近的动作（差距在 5 以内）
        threshold = best_score - 5.0
        top_moves = [m for m, s in move_scores if s >= threshold]
        # 如果只有一个或分数差距很大，就直接选最优
        if len(top_moves) == 1 or (move_scores[0][1] - move_scores[1][1] > 20):
            return move_scores[0][0]
        else:
            return rng.choice(top_moves)

    # 困难模式：直接选最优，确定性
    return move_scores[0][0]
