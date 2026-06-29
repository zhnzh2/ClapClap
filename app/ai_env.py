"""Minimal ClapClap 1.0 training/evaluation environment.

This module intentionally avoids third-party RL dependencies. It provides a
small, stable interface that future Gymnasium/PettingZoo wrappers can adapt.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Literal

from app.ai.engine import get_legal_action_mask, get_legal_moves_list
from app.ai.space import get_index_by_move, get_move_by_index
from app.v1.constants import Move
from app.v1.game import GameEngine
from app.v1.models import GameState

Seat = Literal[1, 2]
OpponentPolicy = Callable[[GameState, Seat, random.Random], Move]


def random_opponent_policy(state: GameState, controlled_player: Seat, rng: random.Random) -> Move:
    legal = get_legal_moves_list(state, controlled_player)
    return rng.choice(legal)


@dataclass
class StepResult:
    observation: dict
    reward: float
    terminated: bool
    truncated: bool
    info: dict = field(default_factory=dict)


class ClapClapEnv:
    """One-agent 1.0 environment where the opponent is supplied by a policy."""

    observation_version = "clapclap-v1-public-state-v1"

    def __init__(
        self,
        *,
        ai_player: Seat = 1,
        opponent_policy: OpponentPolicy = random_opponent_policy,
        max_rounds: int = 200,
        seed: int | None = None,
    ) -> None:
        if ai_player not in (1, 2):
            raise ValueError(f"ai_player 必须为 1 或 2，收到: {ai_player}")
        if max_rounds <= 0:
            raise ValueError("max_rounds 必须大于 0。")

        self.ai_player: Seat = ai_player
        self.opponent_policy = opponent_policy
        self.max_rounds = max_rounds
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

    def encode_observation(self) -> dict:
        self_state = self.state.p1 if self.ai_player == 1 else self.state.p2
        opponent_state = self.state.p2 if self.ai_player == 1 else self.state.p1
        return {
            "version": self.observation_version,
            "ai_player": self.ai_player,
            "round_num": self.state.round_num,
            "self": self_state.to_dict(),
            "opponent": opponent_state.to_dict(),
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
