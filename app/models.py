from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.constants import (
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
    def from_dict(cls, data: dict) -> "PlayerState":
        return cls(
            hp=data.get("hp", INITIAL_HP),
            qi=data.get("qi", INITIAL_QI),
            shield=data.get("shield", INITIAL_SHIELD),
            spark=data.get("spark", INITIAL_SPARK),
            battery=data.get("battery", INITIAL_BATTERY),
            pickaxe=data.get("pickaxe", INITIAL_PICKAXE),
            flash_used=data.get("flash_used", 0),
        )

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
        if not isinstance(data, dict):
            raise TypeError("RoundLog 数据必须是 dict。")

        p1_after = data.get("p1_after", {})
        p2_after = data.get("p2_after", {})

        if not isinstance(p1_after, dict):
            p1_after = {}
        if not isinstance(p2_after, dict):
            p2_after = {}

        raw_p1_move = data.get("p1_move")
        raw_p2_move = data.get("p2_move")

        try:
            p1_move = Move[raw_p1_move] if isinstance(raw_p1_move, str) else Move.QI
        except KeyError:
            try:
                p1_move = Move(raw_p1_move)
            except Exception:
                p1_move = Move.QI

        try:
            p2_move = Move[raw_p2_move] if isinstance(raw_p2_move, str) else Move.QI
        except KeyError:
            try:
                p2_move = Move(raw_p2_move)
            except Exception:
                p2_move = Move.QI

        return cls(
            round_num=data.get("round_num", 0),

            p1_move=p1_move,
            p2_move=p2_move,

            p1_valid=data.get("p1_valid", True),
            p2_valid=data.get("p2_valid", True),

            p1_damage_taken=data.get("p1_damage_taken", 0),
            p2_damage_taken=data.get("p2_damage_taken", 0),

            p1_pickaxe_blocked=data.get("p1_pickaxe_blocked", 0),
            p2_pickaxe_blocked=data.get("p2_pickaxe_blocked", 0),

            p1_note=data.get("p1_note", ""),
            p2_note=data.get("p2_note", ""),
            summary=data.get("summary", ""),

            p1_hp_after=p1_after.get("hp", data.get("p1_hp_after", 0)),
            p2_hp_after=p2_after.get("hp", data.get("p2_hp_after", 0)),
            p1_qi_after=p1_after.get("qi", data.get("p1_qi_after", 0)),
            p2_qi_after=p2_after.get("qi", data.get("p2_qi_after", 0)),
            p1_shield_after=p1_after.get("shield", data.get("p1_shield_after", 0)),
            p2_shield_after=p2_after.get("shield", data.get("p2_shield_after", 0)),
            p1_spark_after=p1_after.get("spark", data.get("p1_spark_after", 0)),
            p2_spark_after=p2_after.get("spark", data.get("p2_spark_after", 0)),
            p1_battery_after=p1_after.get("battery", data.get("p1_battery_after", 0)),
            p2_battery_after=p2_after.get("battery", data.get("p2_battery_after", 0)),
            p1_pickaxe_after=p1_after.get("pickaxe", data.get("p1_pickaxe_after", 0)),
            p2_pickaxe_after=p2_after.get("pickaxe", data.get("p2_pickaxe_after", 0)),

            winner_after_round=data.get("winner_after_round"),
        )

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
    def from_dict(cls, data: dict) -> "GameState":
        state = cls()
        state.round_num = data.get("round_num", 1)
        state.winner = data.get("winner")

        p1_data = data.get("p1", {})
        p2_data = data.get("p2", {})

        if not isinstance(p1_data, dict):
            p1_data = {}
        if not isinstance(p2_data, dict):
            p2_data = {}

        state.p1 = PlayerState.from_dict(p1_data)
        state.p2 = PlayerState.from_dict(p2_data)

        raw_history = data.get("history", [])
        state.history = []

        if isinstance(raw_history, list):
            for item in raw_history:
                try:
                    state.history.append(RoundLog.from_dict(item))
                except Exception:
                    continue

        return state