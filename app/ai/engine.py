"""
ClapClap 1.0 AI 引擎。

提供：
  - get_legal_action_mask: 合法动作掩码（长度 17 的布尔列表）
  - get_player_view: 玩家视角转换（self / opponent / round_num / mask）
  - select_move: 统一 AI 策略接口

AI 不重新实现规则，所有合法性判断和结算都通过现有 app/v1/ 规则引擎。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from app.v1.constants import Move
from app.v1.game import GameEngine
from app.v1.models import GameState, PlayerState
from app.ai.space import (
    ACTION_SPACE_SIZE,
    get_move_by_index,
)


# ---------------------------------------------------------------------------
# 合法动作掩码
# ---------------------------------------------------------------------------


def _get_player_state(state: GameState, controlled_player: int) -> PlayerState:
    if controlled_player == 1:
        return state.p1
    if controlled_player == 2:
        return state.p2
    raise ValueError(f"controlled_player 必须为 1 或 2，收到: {controlled_player}")


def get_legal_action_mask(state: GameState, controlled_player: int) -> List[bool]:
    """
    返回长度为 17 的布尔列表。

    mask[i] == True 表示 action_index=i 的动作对 controlled_player 合法。

    合法性判断完全来自 GameEngine.can_afford()，不自行推导资源规则。
    """
    player = _get_player_state(state, controlled_player)
    mask: List[bool] = []
    for i in range(ACTION_SPACE_SIZE):
        move = get_move_by_index(i)
        mask.append(GameEngine.can_afford(player, move))
    return mask


def get_legal_moves_list(state: GameState, controlled_player: int) -> List[Move]:
    """
    返回 controlled_player 当前合法动作的 Move 列表。
    便捷函数，内部调用 get_legal_action_mask 再转换。
    """
    mask = get_legal_action_mask(state, controlled_player)
    return [get_move_by_index(i) for i, ok in enumerate(mask) if ok]


# ---------------------------------------------------------------------------
# 玩家视角转换
# ---------------------------------------------------------------------------


def get_player_view(state: GameState, controlled_player: int) -> Dict[str, Any]:
    """
    将 GameState 转换为 AI 统一视角，消除 P1/P2 差异。

    参数:
        state: 当前游戏状态（不会被修改）。
        controlled_player: 1 表示 AI 控制 P1，2 表示 AI 控制 P2。

    返回:
        {
            "self": PlayerState,              # AI 控制方的状态
            "opponent": PlayerState,          # 对手的状态
            "round_num": int,
            "legal_action_mask": list[bool],  # 长度 17
            "legal_actions": list[Move],      # AI 合法动作列表
        }
    """
    _get_player_state(state, controlled_player)
    if controlled_player == 1:
        self_p = state.p1.copy()
        opponent_p = state.p2.copy()
    else:
        self_p = state.p2.copy()
        opponent_p = state.p1.copy()

    return {
        "self": self_p,
        "opponent": opponent_p,
        "round_num": state.round_num,
        "legal_action_mask": get_legal_action_mask(state, controlled_player),
        "legal_actions": get_legal_moves_list(state, controlled_player),
    }


# ---------------------------------------------------------------------------
# 统一策略接口
# ---------------------------------------------------------------------------


def select_move(
    state: GameState,
    controlled_player: int,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> Move:
    """
    统一 AI 策略接口。

    所有 AI 策略（随机、启发式、未来模型推理）都通过此接口调用。

    参数:
        state: 当前 GameState —— 不会被修改。
        controlled_player: 1 或 2，表示 AI 控制 P1 还是 P2。
        rng: random.Random 实例，用于可复现的随机决策。
        config: 可选配置字典。当前支持的键:
            - difficulty: "easy" | "normal" | "hard"（默认 "easy"）

    返回:
        Move: AI 选择的动作，保证对 controlled_player 合法。

    异常:
        ValueError: 无合法动作可选（理论上不应出现，因 QI/SHIELD 永远合法）。
        ValueError: 未知难度。
    """
    config = config or {}
    difficulty = config.get("difficulty", "easy")

    # 1. 获取合法动作
    mask = get_legal_action_mask(state, controlled_player)
    legal_indices = [i for i, ok in enumerate(mask) if ok]

    if not legal_indices:
        raise ValueError(
            f"AI (P{controlled_player}) 在当前状态下无合法动作可选。"
            f" flash_used={state.p1.flash_used if controlled_player == 1 else state.p2.flash_used}"
        )

    # 2. 根据难度选择策略
    if difficulty == "easy":
        return _random_strategy(legal_indices, rng)

    if difficulty == "normal":
        from app.ai.strategies import heuristic_select_move
        return heuristic_select_move(state, controlled_player, rng, {
            "conservative": False,
            **(config or {}),
        })

    if difficulty == "hard":
        from app.ai.strategies import heuristic_select_move
        return heuristic_select_move(state, controlled_player, rng, {
            "conservative": True,
            **(config or {}),
        })

    raise ValueError(f"未知难度: {difficulty}")


# ---------------------------------------------------------------------------
# 策略实现（内部）
# ---------------------------------------------------------------------------


def _random_strategy(legal_indices: List[int], rng: random.Random) -> Move:
    """
    随机合法动作策略。

    从合法动作中等概率随机选择一个。用于：
      - 简单难度
      - 验证动作空间和合法动作掩码
      - 自动对战压力测试
    """
    chosen_idx = rng.choice(legal_indices)
    return get_move_by_index(chosen_idx)
