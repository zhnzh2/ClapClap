from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from constants import (
    INITIAL_BATTERY,
    INITIAL_HP,
    INITIAL_PICKAXE,
    INITIAL_QI,
    INITIAL_SHIELD,
    INITIAL_SPARK,
    MAX_FLASH_USE,
    Move,
)


@dataclass
class PlayerState:
    hp: int = INITIAL_HP
    qi: int = INITIAL_QI
    shield: int = INITIAL_SHIELD
    spark: int = INITIAL_SPARK
    battery: int = INITIAL_BATTERY
    pickaxe: int = INITIAL_PICKAXE

    flash_used: int = 0

    def copy(self) -> "PlayerState":
        return PlayerState(
            hp=self.hp,
            qi=self.qi,
            shield=self.shield,
            spark=self.spark,
            battery=self.battery,
            pickaxe=self.pickaxe,
            flash_used=self.flash_used,
        )

    def can_use_flash(self) -> bool:
        return self.flash_used < MAX_FLASH_USE


@dataclass
class RoundLog:
    round_num: int

    p1_move: Move
    p2_move: Move

    p1_valid: bool = True
    p2_valid: bool = True

    p1_damage_taken: int = 0
    p2_damage_taken: int = 0

    p1_pickaxe_blocked: int = 0
    p2_pickaxe_blocked: int = 0

    p1_note: str = ""
    p2_note: str = ""
    summary: str = ""

    p1_hp_after: int = 0
    p2_hp_after: int = 0
    p1_qi_after: int = 0
    p2_qi_after: int = 0
    p1_shield_after: int = 0
    p2_shield_after: int = 0
    p1_spark_after: int = 0
    p2_spark_after: int = 0
    p1_battery_after: int = 0
    p2_battery_after: int = 0
    p1_pickaxe_after: int = 0
    p2_pickaxe_after: int = 0

    winner_after_round: Optional[int] = None
    # 约定：
    # None -> 未结束
    # 1    -> P1 胜
    # 2    -> P2 胜
    # 0    -> 双败 / 平局


@dataclass
class GameState:
    p1: PlayerState = field(default_factory=PlayerState)
    p2: PlayerState = field(default_factory=PlayerState)

    round_num: int = 0
    winner: Optional[int] = None
    history: list[RoundLog] = field(default_factory=list)

    def copy(self) -> "GameState":
        return GameState(
            p1=self.p1.copy(),
            p2=self.p2.copy(),
            round_num=self.round_num,
            winner=self.winner,
            history=list(self.history),
        )