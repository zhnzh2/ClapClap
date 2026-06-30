"""Minimal ClapClap 1.0 training/evaluation environment.

This module intentionally avoids third-party RL dependencies. It provides a
small, stable interface that future Gymnasium/PettingZoo wrappers can adapt.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Literal

from app.ai.engine import get_legal_action_mask, get_legal_moves_list
from app.ai.space import (
    ACTION_SPACE_SIZE,
    get_action_space_fingerprint,
    get_index_by_move,
    get_move_by_index,
    get_moves_in_order,
    validate_action_space,
)
from app.v1.constants import Move
from app.v1.game import GameEngine
from app.v1.models import GameState

Seat = Literal[1, 2]
OpponentPolicy = Callable[[GameState, Seat, random.Random], Move]
OBSERVATION_VERSION = "clapclap-v1-public-state-v2"
REWARD_CONFIG_VERSION = "terminal-v1"
DEFAULT_HISTORY_WINDOW = 4


def random_opponent_policy(state: GameState, controlled_player: Seat, rng: random.Random) -> Move:
    legal = get_legal_moves_list(state, controlled_player)
    return rng.choice(legal)


def normal_heuristic_policy(state: GameState, controlled_player: Seat, rng: random.Random) -> Move:
    """Normal 难度启发式策略（conservative=False）。"""
    from app.ai.engine import select_move
    return select_move(state.copy(), controlled_player, rng, {"difficulty": "normal"})


def hard_heuristic_policy(state: GameState, controlled_player: Seat, rng: random.Random) -> Move:
    """Hard 难度启发式策略（conservative=True）。"""
    from app.ai.engine import select_move
    return select_move(state.copy(), controlled_player, rng, {"difficulty": "hard"})


def make_opponent_pool(
    policies: list[OpponentPolicy],
    weights: list[float] | None = None,
    *,
    seed: int | None = None,
) -> OpponentPolicy:
    """创建一个对手池策略：每局开始时随机选一个子策略，局内固定。

    参数
    ----------
    policies : 子策略列表。
    weights : 抽样权重，默认均匀。
    seed : 池内抽样的随机种子（与对局内 RNG 分离）。
    """
    import random as _random
    pool_rng = _random.Random(seed)

    # 用可变容器保存当前局所选策略，reset 时通过 round_num==0 重新抽样
    current: list[OpponentPolicy | None] = [None]

    def pooled(state: GameState, player: Seat, rng: random.Random) -> Move:
        if state.round_num == 0 or current[0] is None:
            current[0] = pool_rng.choices(policies, weights=weights, k=1)[0]
        return current[0](state, player, rng)

    return pooled


# 预置对手池
DEFAULT_OPPONENT_POOL = make_opponent_pool(
    policies=[random_opponent_policy, normal_heuristic_policy, hard_heuristic_policy],
    weights=[0.2, 0.4, 0.4],
    seed=20260630,
)


@dataclass
class StepResult:
    observation: dict
    reward: float
    terminated: bool
    truncated: bool
    info: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EnvMetadata:
    rule_version: str
    action_space_size: int
    action_space_fingerprint: str
    action_names: list[str]
    observation_version: str
    reward_config_version: str
    history_window: int
    max_rounds: int

    def to_dict(self) -> dict:
        return {
            "rule_version": self.rule_version,
            "action_space_size": self.action_space_size,
            "action_space_fingerprint": self.action_space_fingerprint,
            "action_names": list(self.action_names),
            "observation_version": self.observation_version,
            "reward_config_version": self.reward_config_version,
            "history_window": self.history_window,
            "max_rounds": self.max_rounds,
        }


class ClapClapEnv:
    """One-agent 1.0 environment where the opponent is supplied by a policy."""

    rule_version = "1.0"
    observation_version = OBSERVATION_VERSION
    reward_config_version = REWARD_CONFIG_VERSION

    def __init__(
        self,
        *,
        ai_player: Seat = 1,
        opponent_policy: OpponentPolicy = random_opponent_policy,
        max_rounds: int = 200,
        history_window: int = DEFAULT_HISTORY_WINDOW,
        seed: int | None = None,
    ) -> None:
        if ai_player not in (1, 2):
            raise ValueError(f"ai_player 必须为 1 或 2，收到: {ai_player}")
        if max_rounds <= 0:
            raise ValueError("max_rounds 必须大于 0。")
        if history_window < 0:
            raise ValueError("history_window 不能小于 0。")

        self.ai_player: Seat = ai_player
        self.opponent_policy = opponent_policy
        self.max_rounds = max_rounds
        self.history_window = history_window
        self.rng = random.Random(seed)
        self.state = GameState()

    @property
    def opponent_player(self) -> Seat:
        return 2 if self.ai_player == 1 else 1

    def reset(self, *, seed: int | None = None, ai_player: Seat | None = None) -> dict:
        if seed is not None:
            self.rng.seed(seed)
        if ai_player is not None:
            if ai_player not in (1, 2):
                raise ValueError(f"ai_player 必须为 1 或 2，收到: {ai_player}")
            self.ai_player = ai_player
        self.state = GameState()
        return self.encode_observation()

    def legal_action_mask(self) -> list[bool]:
        return get_legal_action_mask(self.state, self.ai_player)

    def metadata(self) -> dict:
        return EnvMetadata(
            rule_version=self.rule_version,
            action_space_size=ACTION_SPACE_SIZE,
            action_space_fingerprint=get_action_space_fingerprint(),
            action_names=[move.name for move in get_moves_in_order()],
            observation_version=self.observation_version,
            reward_config_version=self.reward_config_version,
            history_window=self.history_window,
            max_rounds=self.max_rounds,
        ).to_dict()

    def observation_space_schema(self) -> dict:
        player_fields = {
            "hp": "int",
            "qi": "int",
            "shield": "int",
            "spark": "int",
            "battery": "int",
            "pickaxe": "int",
            "flash_used": "int",
        }
        return {
            "version": self.observation_version,
            "ai_player": "1|2",
            "round_num": "int",
            "self": player_fields,
            "opponent": player_fields,
            "history": "list[round_log] newest-trimmed-by-history_window",
            "legal_action_mask": f"list[bool] length={ACTION_SPACE_SIZE}",
        }

    def encode_observation(self) -> dict:
        self_state = self.state.p1 if self.ai_player == 1 else self.state.p2
        opponent_state = self.state.p2 if self.ai_player == 1 else self.state.p1
        if self.history_window == 0:
            history = []
        else:
            history = [
                item.to_dict()
                for item in self.state.history[-self.history_window:]
            ]
        return {
            "version": self.observation_version,
            "metadata": self.metadata(),
            "ai_player": self.ai_player,
            "round_num": self.state.round_num,
            "self": self_state.to_dict(),
            "opponent": opponent_state.to_dict(),
            "history": history,
            "legal_action_mask": self.legal_action_mask(),
        }

    def step(self, action_index: int) -> StepResult:
        if self.state.winner is not None:
            return StepResult(
                observation=self.encode_observation(),
                reward=self._reward(),
                terminated=True,
                truncated=False,
                info={"winner": self.state.winner, "already_terminal": True},
            )

        move = get_move_by_index(action_index)
        if not self.legal_action_mask()[action_index]:
            raise ValueError(f"动作 {move.name} 对当前 AI 玩家不合法。")

        round_start = self.state.copy()
        opponent_move = self.opponent_policy(round_start, self.opponent_player, self.rng)

        if self.ai_player == 1:
            p1_move, p2_move = move, opponent_move
        else:
            p1_move, p2_move = opponent_move, move

        GameEngine.resolve_round(self.state, p1_move, p2_move)
        truncated = self.state.winner is None and self.state.round_num >= self.max_rounds
        terminated = self.state.winner is not None

        return StepResult(
            observation=self.encode_observation(),
            reward=self._reward(truncated=truncated),
            terminated=terminated,
            truncated=truncated,
            info={
                "ai_move": move.name,
                "opponent_move": opponent_move.name,
                "winner": self.state.winner,
                "reward_config_version": self.reward_config_version,
            },
        )

    def _reward(self, *, truncated: bool = False) -> float:
        if truncated:
            return 0.0
        winner = self.state.winner
        if winner is None:
            return 0.0
        if winner == self.ai_player:
            return 1.0
        return -1.0


def action_index(move: Move) -> int:
    return get_index_by_move(move)


def validate_model_metadata(metadata: dict) -> bool:
    """Return whether saved model metadata matches the current 1.0 env contract."""
    return (
        metadata.get("rule_version") == ClapClapEnv.rule_version
        and validate_action_space(
            metadata.get("action_space_size"),
            metadata.get("action_space_fingerprint"),
        )
        and metadata.get("observation_version") == ClapClapEnv.observation_version
        and metadata.get("reward_config_version") == ClapClapEnv.reward_config_version
    )
