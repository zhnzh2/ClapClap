"""
ClapClap 2.0 AI 策略。

提供：
  - select_ai_move_v2: 为 v2 玩家选择合法动作
  - get_legal_moves_v2_ai: 获取指定玩家的合法动作列表

AI 只通过 GameEngineV2 公开接口访问规则引擎，不接触本回合其他玩家未公开动作。
"""

from __future__ import annotations

import random
from typing import Optional

from app.v2.constants import Move
from app.v2.game import GameEngineV2
from app.v2.models import GameStateV2, PlayerStateV2


# ---------------------------------------------------------------------------
# 合法动作
# ---------------------------------------------------------------------------

def get_legal_moves_v2_ai(state: GameStateV2, player_id: str) -> list[Move]:
    """获取指定玩家的合法动作列表。

    合法性判断完全来自 GameEngineV2.can_afford()，不自行推导规则。
    """
    player = state.get_player(player_id)
    if player is None or not player.is_alive():
        return []
    legal: list[Move] = []
    for move in Move:
        if GameEngineV2.can_afford(player, move):
            legal.append(move)
    return legal


def get_legal_move_names_v2_ai(state: GameStateV2, player_id: str) -> list[str]:
    """获取指定玩家的合法动作名列表（用于 API 返回）。"""
    return [m.name for m in get_legal_moves_v2_ai(state, player_id)]


# ---------------------------------------------------------------------------
# AI 策略
# ---------------------------------------------------------------------------

def select_ai_move_v2(
    state: GameStateV2,
    player_id: str,
    difficulty: str = "normal",
    rng: random.Random | None = None,
) -> Move:
    """为指定玩家选择合法动作。

    AI 不接触本回合其他玩家的未公开动作，只基于：
      - 当前 GameStateV2 公开信息
      - 目标玩家的 PlayerStateV2 资源状态

    Args:
        state: 当前对局状态（回合开始时的快照）
        player_id: 目标玩家 ID
        difficulty: "random" | "normal"
        rng: 可选随机数生成器（用于可复现测试）

    Returns:
        选择的 Move 枚举值
    """
    legal = get_legal_moves_v2_ai(state, player_id)
    if not legal:
        # 无合法动作时返回 QI（通常不会发生，因为 QI 总是合法）
        return Move.QI

    _rng = rng if rng is not None else random.Random()

    if difficulty == "random":
        return _rng.choice(legal)

    if difficulty == "normal":
        return _select_normal_heuristic(state, player_id, legal, _rng)

    # 未知难度回退 random
    return _rng.choice(legal)


def _select_normal_heuristic(
    state: GameStateV2,
    player_id: str,
    legal: list[Move],
    rng: random.Random,
) -> Move:
    """轻量 heuristic：基于资源和局势做简单决策。

    优先级（从高到低）：
      1. 攻击：有足够资源时用破/闪电
      2. 防御：盾系资源充足时铸盾
      3. 资源：攒气/盾
    """
    player = state.get_player(player_id)
    if player is None:
        return Move.QI

    legal_set = set(legal)

    # 统计存活对手数
    alive_opponents = [
        p for p in state.alive_players()
        if p.player_id != player_id
    ]
    opponent_count = len(alive_opponents)
    is_last_two = opponent_count == 1

    # ── 攻击优先 ──
    # 破：最通用的攻击，qi >= 2
    if Move.PO in legal_set and player.qi >= 2:
        # 剩两人时更激进
        if is_last_two or rng.random() < 0.7:
            return Move.PO

    # 闪电：shield >= 3
    if Move.SHAN_DIAN in legal_set and player.shield >= 3:
        if rng.random() < 0.6:
            return Move.SHAN_DIAN

    # gi：qi >= 1，基础攻击
    if Move.GI in legal_set and player.qi >= 1:
        # 避免在有更好选择时用 gi
        if Move.PO not in legal_set and rng.random() < 0.5:
            return Move.GI

    # 冷锋：qi >= 3
    if Move.LENG_FENG in legal_set and player.qi >= 3:
        if rng.random() < 0.4:
            return Move.LENG_FENG

    # Fire：shield >= 2
    if Move.FIRE in legal_set and player.shield >= 2:
        if rng.random() < 0.4:
            return Move.FIRE

    # 如来：qi >= 5，高伤害
    if Move.RU_LAI in legal_set and player.qi >= 5:
        return Move.RU_LAI

    # Shining：shield 或 spark/battery
    if Move.SHINING in legal_set:
        if player.shield >= 4 or player.spark >= 1:
            return Move.SHINING

    # 烈焰：qi >= 3 或 有 spark
    if Move.LIE_YAN in legal_set:
        if player.qi >= 3 or player.spark >= 1:
            if rng.random() < 0.5:
                return Move.LIE_YAN

    # 黑洞：qi >= 8，终极武器
    if Move.HEI_DONG in legal_set:
        return Move.HEI_DONG

    # ── 防御 ──
    # 十字：qi >= 2
    if Move.SHI_ZI in legal_set and player.qi >= 2 and player.hp <= 1:
        if rng.random() < 0.5:
            return Move.SHI_ZI

    # 八卦：qi >= 3
    if Move.BA_GUA in legal_set and player.qi >= 3 and player.hp <= 1:
        if rng.random() < 0.5:
            return Move.BA_GUA

    # ── 锦囊 ──
    # 镐：qi >= 2
    if Move.GAO in legal_set and player.qi >= 2:
        if rng.random() < 0.25:
            return Move.GAO

    # ── 资源攒气/盾 ──
    # 优先攒气（用于后续攻击）
    if Move.QI in legal_set:
        return Move.QI

    # 盾
    if Move.SHIELD in legal_set:
        return Move.SHIELD

    # ── 兜底：从合法动作中随机选 ──
    return rng.choice(legal)
