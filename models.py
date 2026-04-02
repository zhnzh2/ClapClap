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

    def to_dict(self) -> dict:
        return {
            "hp": self.hp,
            "qi": self.qi,
            "shield": self.shield,
            "spark": self.spark,
            "battery": self.battery,
            "pickaxe": self.pickaxe,
            "flash_used": self.flash_used,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        state = cls()
        state.round_num = data["round_num"]
        state.winner = data["winner"]
        state.p1 = PlayerState.from_dict(data["p1"])
        state.p2 = PlayerState.from_dict(data["p2"])
        state.history = [RoundLog.from_dict(item) for item in data.get("history", [])]
        return state

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

    def to_dict(self) -> dict:
        return {
            "round_num": self.round_num,
            "p1_move": self.p1_move.name,
            "p1_move_label": self.p1_move.value,
            "p2_move": self.p2_move.name,
            "p2_move_label": self.p2_move.value,
            "p1_valid": self.p1_valid,
            "p2_valid": self.p2_valid,
            "p1_damage_taken": self.p1_damage_taken,
            "p2_damage_taken": self.p2_damage_taken,
            "p1_pickaxe_blocked": self.p1_pickaxe_blocked,
            "p2_pickaxe_blocked": self.p2_pickaxe_blocked,
            "p1_note": self.p1_note,
            "p2_note": self.p2_note,
            "summary": self.summary,
            "p1_after": {
                "hp": self.p1_hp_after,
                "qi": self.p1_qi_after,
                "shield": self.p1_shield_after,
                "spark": self.p1_spark_after,
                "battery": self.p1_battery_after,
                "pickaxe": self.p1_pickaxe_after,
            },
            "p2_after": {
                "hp": self.p2_hp_after,
                "qi": self.p2_qi_after,
                "shield": self.p2_shield_after,
                "spark": self.p2_spark_after,
                "battery": self.p2_battery_after,
                "pickaxe": self.p2_pickaxe_after,
            },
            "winner_after_round": self.winner_after_round,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RoundLog":
        return cls(**data)

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
    
    def to_dict(self, include_history: bool = True) -> dict:
        data = {
            "round_num": self.round_num,
            "winner": self.winner,
            "p1": self.p1.to_dict(),
            "p2": self.p2.to_dict(),
        }

        if include_history:
            data["history"] = [log.to_dict() for log in self.history]

        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "PlayerState":
        return cls(
            hp=data["hp"],
            qi=data["qi"],
            shield=data["shield"],
            spark=data["spark"],
            battery=data["battery"],
            pickaxe=data["pickaxe"],
            flash_used=data["flash_used"],
        )