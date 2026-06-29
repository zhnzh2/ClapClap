"""
ClapClap 2.0 多人版数据模型。

与 1.0 (app/models.py) 完全独立。
所有结构以「玩家列表」替代 p1/p2 双人假设。

设计分层：
  - PlayerStateV2: 跨回合持久状态（资源、身份、生死）
  - RoundMoveRecordV2: 单回合内一个玩家的动作和结算状态
  - SpeedLayerEvent: 某个速度层中的一个原子事件
  - RoundLogV2: 完整回合记录（含所有速度层事件序列）
  - GameStateV2: 对局总状态（含玩家列表 + 阶段机 + 历史）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.v2.constants import (
    INITIAL_BATTERY,
    INITIAL_HP,
    INITIAL_PICKAXE,
    INITIAL_QI,
    INITIAL_SHIELD,
    INITIAL_SPARK,
    MAX_FLASH_USE,
)
from app.v2.constants import (
    DEATH_NORMAL,
    PLAYER_ALIVE,
    PLAYER_DEAD,
    PLAYER_UNRESOLVED,
    PLAYER_RESOLVED,
    PHASE_WAITING_MOVES,
    STEP_ACTION_WAITING,
)

ROOM_ROLE_PLAYER = "player"
ROOM_ROLE_SPECTATOR = "spectator"


# ═══════════════════════════════════════════════════════════════
# 玩家状态（跨回合持久）
# ═══════════════════════════════════════════════════════════════

@dataclass
class PlayerStateV2:
    """2.0 玩家状态。

    持久字段（保存到对局记录）：
      - 身份、资源、生死状态
      - 死亡信息、最终名次

    运行时字段（每回合重置，不持久化）：
      - 本回合动作、提交/公开状态
      - 已操作/未操作状态
      - 目标意向
    """

    # ── 身份 ──
    player_id: str = ""                     # 对局内稳定标识
    seat_index: int = 0                     # 加入顺序（0-based）
    username: str = ""                      # 显示名

    # ── 资源（与 1.0 一致） ──
    hp: int = INITIAL_HP
    qi: int = INITIAL_QI
    shield: int = INITIAL_SHIELD
    spark: int = INITIAL_SPARK
    battery: int = INITIAL_BATTERY
    pickaxe: int = INITIAL_PICKAXE
    flash_used: int = 0

    # ── 生死状态与房间身份 ──
    status: str = PLAYER_ALIVE              # alive / dead
    room_role: str = ROOM_ROLE_PLAYER       # player / spectator
    death_round: int | None = None          # 死亡回合
    death_cause: str | None = None          # 死亡原因代码
    death_speed_layer: int | None = None    # 死亡所在速度层（爆镐用）
    final_rank: int | None = None           # 最终名次（游戏结束时赋值）

    # ── 运行时：本回合动作（每回合重置） ──
    pending_move: str | None = None         # 本回合提交的手势名
    move_submitted: bool = False            # 是否已提交
    move_revealed: bool = False             # 是否已亮招

    # ── 运行时：结算状态（每回合重置） ──
    resolution_status: str = PLAYER_UNRESOLVED  # unresolved / resolved
    is_flashed: bool = False                # 是否使用了闪（本回合）

    # ── 运行时：目标选择（每速度层重置） ──
    target_intent: list[str] = field(default_factory=list)   # 初始目标意向 [player_id, ...]
    target_final: list[str] = field(default_factory=list)    # 最终目标 [player_id, ...]
    layer_confirmed: bool = False           # 本速度层是否已确认

    def can_use_flash(self) -> bool:
        return self.flash_used < MAX_FLASH_USE

    def is_alive(self) -> bool:
        return self.status == PLAYER_ALIVE

    def is_dead(self) -> bool:
        return self.status == PLAYER_DEAD

    def is_spectating(self) -> bool:
        return self.room_role == ROOM_ROLE_SPECTATOR

    def is_resolved(self) -> bool:
        return self.resolution_status == PLAYER_RESOLVED

    def is_unresolved(self) -> bool:
        return self.resolution_status == PLAYER_UNRESOLVED

    def mark_resolved(self) -> None:
        """标记为已操作对象。"""
        self.resolution_status = PLAYER_RESOLVED

    def mark_dead(self, round_num: int, cause: str, speed_layer: int | None = None) -> None:
        """标记死亡。"""
        self.status = PLAYER_DEAD
        self.hp = 0
        self.death_round = round_num
        self.death_cause = cause
        self.death_speed_layer = speed_layer

    def mark_spectating(self) -> None:
        """转为观战身份，不改变死亡状态。"""
        if self.is_dead():
            self.room_role = ROOM_ROLE_SPECTATOR

    def reset_round_runtime(self) -> None:
        """重置本回合运行时字段（每回合开始时调用）。"""
        self.pending_move = None
        self.move_submitted = False
        self.move_revealed = False
        self.resolution_status = PLAYER_UNRESOLVED
        self.is_flashed = False
        self.target_intent = []
        self.target_final = []
        self.layer_confirmed = False

    def reset_layer_runtime(self) -> None:
        """重置本速度层运行时字段（每层开始时调用）。"""
        self.target_intent = []
        self.target_final = []
        self.layer_confirmed = False

    def resource_snapshot(self) -> dict:
        """当前资源快照。"""
        return {
            "hp": self.hp,
            "qi": self.qi,
            "shield": self.shield,
            "spark": self.spark,
            "battery": self.battery,
            "pickaxe": self.pickaxe,
            "flash_used": self.flash_used,
        }

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "seat_index": self.seat_index,
            "username": self.username,
            "hp": self.hp,
            "qi": self.qi,
            "shield": self.shield,
            "spark": self.spark,
            "battery": self.battery,
            "pickaxe": self.pickaxe,
            "flash_used": self.flash_used,
            "status": self.status,
            "room_role": self.room_role,
            "death_round": self.death_round,
            "death_cause": self.death_cause,
            "death_speed_layer": self.death_speed_layer,
            "final_rank": self.final_rank,
            "pending_move": self.pending_move,
            "move_submitted": self.move_submitted,
            "move_revealed": self.move_revealed,
            "resolution_status": self.resolution_status,
            "is_flashed": self.is_flashed,
            "target_intent": self.target_intent,
            "target_final": self.target_final,
            "layer_confirmed": self.layer_confirmed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerStateV2":
        status = data.get("status", PLAYER_ALIVE)
        room_role = data.get("room_role", ROOM_ROLE_PLAYER)
        # Early drafts used status="spectating"; keep those records readable.
        if status == "spectating":
            status = PLAYER_DEAD
            room_role = ROOM_ROLE_SPECTATOR

        return cls(
            player_id=data.get("player_id", ""),
            seat_index=data.get("seat_index", 0),
            username=data.get("username", ""),
            hp=data.get("hp", INITIAL_HP),
            qi=data.get("qi", INITIAL_QI),
            shield=data.get("shield", INITIAL_SHIELD),
            spark=data.get("spark", INITIAL_SPARK),
            battery=data.get("battery", INITIAL_BATTERY),
            pickaxe=data.get("pickaxe", INITIAL_PICKAXE),
            flash_used=data.get("flash_used", 0),
            status=status,
            room_role=room_role,
            death_round=data.get("death_round"),
            death_cause=data.get("death_cause"),
            death_speed_layer=data.get("death_speed_layer"),
            final_rank=data.get("final_rank"),
            pending_move=data.get("pending_move"),
            move_submitted=data.get("move_submitted", False),
            move_revealed=data.get("move_revealed", False),
            resolution_status=data.get("resolution_status", PLAYER_UNRESOLVED),
            is_flashed=data.get("is_flashed", False),
            target_intent=data.get("target_intent", []),
            target_final=data.get("target_final", []),
            layer_confirmed=data.get("layer_confirmed", False),
        )


# ═══════════════════════════════════════════════════════════════
# 速度层事件（原子结算事件）
# ═══════════════════════════════════════════════════════════════

class EventType(Enum):
    """结算事件类型。"""
    # 攻击相关
    ATTACK_HIT = "attack_hit"               # 攻击命中，造成伤害
    ATTACK_BLOCKED = "attack_blocked"        # 攻击被防御力挡住
    ATTACK_MISSED = "attack_missed"         # 攻击放空 / 无合法目标
    ATTACK_NULLIFIED = "attack_nullified"   # 攻击被对掉 / 三连抵消

    # 锦囊相关
    TRICK_CHI_PO = "trick_chi_po"           # 你吃 → 破
    TRICK_CHI_LIGHTNING = "trick_chi_lightning"  # 你吃 → 闪电
    TRICK_SHUANGCHI_SHINING = "trick_shuangchi_shining"  # 双吃 → Shining
    TRICK_SPLIT = "trick_split"             # 拆分声明

    # gi 特殊
    GI_ATTACK_HEIDONG = "gi_attack_heidong" # gi 攻击黑洞（反噬）
    GI_STEAL_PICKAXE = "gi_steal_pickaxe"   # gi 抢镐
    GI_NO_TARGET = "gi_no_target"           # gi 无合法目标

    # 资源
    RESOURCE_GAIN = "resource_gain"         # 获得资源
    RESOURCE_LOSS = "resource_loss"         # 失去资源（消耗）
    PICKAXE_BLOCK = "pickaxe_block"         # 镐抵挡伤害
    PICKAXE_REVIVE = "pickaxe_revive"       # 镐复活（HP≤0时获得镐 → 恢复HP）
    PICKAXE_BOOM = "pickaxe_boom"           # 爆镐

    # 三连
    THREE_CHAIN_FORMED = "three_chain_formed"    # 三连成立
    THREE_CHAIN_SELECT = "three_chain_select"    # 三连人选选择

    # 状态
    DEFENSE_ZERO = "defense_zero"           # 防御归零
    RESOLVED = "resolved"                   # 变为已操作对象
    DEATH = "death"                         # 死亡
    FLASH = "flash"                         # 使用闪


@dataclass
class SpeedLayerEvent:
    """速度层中的一个原子事件。"""
    event_type: EventType
    speed_layer: int                        # 所在速度层
    source_player_id: str | None = None     # 事件发起者
    target_player_id: str | None = None     # 事件目标
    detail: str = ""                        # 人类可读描述
    data: dict = field(default_factory=dict)  # 结构化数据

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "speed_layer": self.speed_layer,
            "source_player_id": self.source_player_id,
            "target_player_id": self.target_player_id,
            "detail": self.detail,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpeedLayerEvent | None":
        try:
            event_type = EventType(data["event_type"])
        except (KeyError, ValueError):
            return None
        return cls(
            event_type=event_type,
            speed_layer=data.get("speed_layer", 0),
            source_player_id=data.get("source_player_id"),
            target_player_id=data.get("target_player_id"),
            detail=data.get("detail", ""),
            data=data.get("data", {}),
        )


# ═══════════════════════════════════════════════════════════════
# 回合记录
# ═══════════════════════════════════════════════════════════════

@dataclass
class RoundLogV2:
    """2.0 多人回合完整记录。

    结构从「双方动作 + 结果」变为「事件化记录」。
    可完整重现整个回合的结算过程。
    """

    round_num: int = 0

    # ── 所有人原始动作 ──
    moves: dict[str, str] = field(default_factory=dict)      # {player_id: move_name}

    # ── 资源检查 ──
    resource_check_ok: dict[str, bool] = field(default_factory=dict)  # {player_id: bool}
    illegal_players: list[str] = field(default_factory=list)          # 爆气/爆盾玩家

    # ── 闪 ──
    flashed_players: list[str] = field(default_factory=list)

    # ── 三连 ──
    three_chain_groups: list[dict] = field(default_factory=list)
    # [{"type": "gi_chi_po", "players": ["A","B","C"], "selection_chain": [{"selector":"A","options":["B","C"],"selected":"B"}]}]
    two_three_chains: bool = False          # 两组独立三连

    # ── 速度层事件序列 ──
    speed_layer_events: list[SpeedLayerEvent] = field(default_factory=list)

    # ── 每层目标声明 ──
    # {layer: {player_id: {move: str, targets: [str, ...]}}}
    target_declarations_by_layer: dict[int, dict] = field(default_factory=dict)

    # ── 每层冲突记录 ──
    # {layer: [ConflictRecord dicts]}
    conflicts_by_layer: dict[int, list] = field(default_factory=dict)

    # ── 决策历史（含自动决策原因） ──
    # [{layer, player_id, decision_type, options: [{id, label}], chosen: [id, ...], reason: str}]
    decision_log: list[dict] = field(default_factory=list)

    # ── 死亡 ──
    deaths: list[dict] = field(default_factory=list)
    # [{"player_id": "A", "cause": "normal", "round": 3, "speed_layer": 9}]

    # ── 回合前后资源快照 ──
    pre_snapshots: dict[str, dict] = field(default_factory=dict)   # {player_id: resource_dict}
    post_snapshots: dict[str, dict] = field(default_factory=dict)  # {player_id: resource_dict}

    # ── 名次更新 ──
    rank_updates: dict[str, int] = field(default_factory=dict)  # {player_id: rank}

    # ── 胜负 ──
    winner: str | None = None               # 获胜者 player_id（None=继续，""=平局）
    game_ended: bool = False

    # ── 聊天（本回合内） ──
    chat: list[dict] = field(default_factory=list)

    def add_event(self, event: SpeedLayerEvent) -> None:
        self.speed_layer_events.append(event)

    def add_death(self, player_id: str, cause: str, speed_layer: int | None = None) -> None:
        self.deaths.append({
            "player_id": player_id,
            "cause": cause,
            "round": self.round_num,
            "speed_layer": speed_layer,
        })

    def record_layer_declarations(self, layer: int, declarations: dict) -> None:
        """记录某速度层的目标声明。"""
        layer_data = {}
        for pid, decl in declarations.items():
            if hasattr(decl, 'to_dict'):
                d = decl.to_dict()
            else:
                d = dict(decl)
            layer_data[pid] = {
                "move": d.get("move_name", ""),
                "targets": d.get("targets", []),
                "is_split": d.get("is_split", False),
                "split_count": d.get("split_count", 1),
            }
        self.target_declarations_by_layer[layer] = layer_data

    def record_layer_conflicts(self, layer: int, conflicts: list) -> None:
        """记录某速度层的冲突。"""
        self.conflicts_by_layer[layer] = [
            c.to_dict() if hasattr(c, 'to_dict') else dict(c)
            for c in conflicts
        ]

    def add_decision(self, layer: int, player_id: str, decision_type: str,
                     options: list, chosen: list, reason: str = "") -> None:
        """记录一次决策。"""
        self.decision_log.append({
            "speed_layer": layer,
            "player_id": player_id,
            "decision_type": decision_type,
            "options": [
                {"id": o.get("option_id", "") if isinstance(o, dict) else o.option_id,
                 "label": o.get("label", "") if isinstance(o, dict) else o.label}
                for o in options
            ],
            "chosen": chosen,
            "reason": reason,
        })

    def to_dict(self) -> dict:
        return {
            "round_num": self.round_num,
            "moves": self.moves,
            "resource_check_ok": self.resource_check_ok,
            "illegal_players": self.illegal_players,
            "flashed_players": self.flashed_players,
            "three_chain_groups": self.three_chain_groups,
            "two_three_chains": self.two_three_chains,
            "speed_layer_events": [e.to_dict() for e in self.speed_layer_events],
            "target_declarations_by_layer": {
                str(layer): decls
                for layer, decls in self.target_declarations_by_layer.items()
            },
            "conflicts_by_layer": {
                str(layer): confs
                for layer, confs in self.conflicts_by_layer.items()
            },
            "decision_log": self.decision_log,
            "deaths": self.deaths,
            "pre_snapshots": self.pre_snapshots,
            "post_snapshots": self.post_snapshots,
            "rank_updates": self.rank_updates,
            "winner": self.winner,
            "game_ended": self.game_ended,
            "chat": self.chat,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoundLogV2":
        log = cls(
            round_num=data.get("round_num", 0),
            moves=data.get("moves", {}),
            resource_check_ok=data.get("resource_check_ok", {}),
            illegal_players=data.get("illegal_players", []),
            flashed_players=data.get("flashed_players", []),
            three_chain_groups=data.get("three_chain_groups", []),
            two_three_chains=data.get("two_three_chains", False),
            deaths=data.get("deaths", []),
            pre_snapshots=data.get("pre_snapshots", {}),
            post_snapshots=data.get("post_snapshots", {}),
            rank_updates=data.get("rank_updates", {}),
            winner=data.get("winner"),
            game_ended=data.get("game_ended", False),
            chat=data.get("chat", []),
        )
        # 重建事件
        for e_data in data.get("speed_layer_events", []):
            event = SpeedLayerEvent.from_dict(e_data)
            if event is not None:
                log.speed_layer_events.append(event)
        # 重建层声明（key 从 str 转回 int）
        for layer_str, decls in data.get("target_declarations_by_layer", {}).items():
            log.target_declarations_by_layer[int(layer_str)] = decls
        for layer_str, confs in data.get("conflicts_by_layer", {}).items():
            log.conflicts_by_layer[int(layer_str)] = confs
        log.decision_log = data.get("decision_log", [])
        return log


# ═══════════════════════════════════════════════════════════════
# 运行时结算结构（不持久化，用于引擎状态机）
# ═══════════════════════════════════════════════════════════════

@dataclass
class TargetDeclaration:
    """单个玩家的目标声明。"""
    player_id: str
    move_name: str                         # 本回合手势
    targets: list[str] = field(default_factory=list)  # 目标 player_id 列表（拆分技能多段）
    is_split: bool = False                 # 是否为拆分技能
    split_count: int = 1                   # 拆分段数

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "move_name": self.move_name,
            "targets": self.targets,
            "is_split": self.is_split,
            "split_count": self.split_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TargetDeclaration":
        return cls(
            player_id=data.get("player_id", ""),
            move_name=data.get("move_name", ""),
            targets=data.get("targets", []),
            is_split=data.get("is_split", False),
            split_count=data.get("split_count", 1),
        )


@dataclass
class ConflictRecord:
    """冲突检测结果。"""
    conflict_type: str = ""                # "mutual" / "multi_attack" / "multi_trick" / "none"
    speed_layer: int = 0
    involved_players: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "conflict_type": self.conflict_type,
            "speed_layer": self.speed_layer,
            "involved_players": self.involved_players,
            "details": self.details,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConflictRecord":
        return cls(
            conflict_type=data.get("conflict_type", ""),
            speed_layer=data.get("speed_layer", 0),
            involved_players=data.get("involved_players", []),
            details=data.get("details", {}),
            resolved=data.get("resolved", False),
        )


@dataclass
class ThreeChainResult:
    """三连结算结果。"""
    found: bool = False
    groups: list[dict] = field(default_factory=list)
    # [{"type": "gi_chi_po", "players": ["A","B","C"]}]
    two_groups: bool = False               # 两组独立三连
    selection_log: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "groups": self.groups,
            "two_groups": self.two_groups,
            "selection_log": self.selection_log,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThreeChainResult":
        return cls(
            found=data.get("found", False),
            groups=data.get("groups", []),
            two_groups=data.get("two_groups", False),
            selection_log=data.get("selection_log", []),
        )


# ═══════════════════════════════════════════════════════════════
# 决策系统：前后端交互数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class DecisionOption:
    """决策选项。"""
    option_id: str = ""                     # 选项 ID（如目标 player_id）
    label: str = ""                         # 显示标签（如用户名）
    is_valid: bool = True                   # 是否合法
    reason: str = ""                        # 不合法原因（可空）

    def to_dict(self) -> dict:
        return {
            "option_id": self.option_id,
            "label": self.label,
            "is_valid": self.is_valid,
            "reason": self.reason,
        }


@dataclass
class DecisionRequest:
    """下发给前端的决策请求。

    当引擎需要玩家输入时生成，通过 Socket.IO 发送给指定玩家。
    """
    decision_id: str = ""                   # 本次决策的唯一 ID
    decision_type: str = ""                 # "target_select" / "three_chain_select" / "conflict_resolve"
    speed_layer: int = 0                    # 所在速度层（三连选人时 speed_layer=2）
    player_id: str = ""                     # 需要做决策的玩家
    prompt: str = ""                        # 人类可读提示
    options: list = field(default_factory=list)  # DecisionOption 列表
    split_count: int = 1                    # 需要选择几段（拆分技能 > 1）
    timeout_seconds: int = 30               # 超时秒数
    negotiation_round: int = 0              # 当前协商轮次（冲突协商时用）

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "speed_layer": self.speed_layer,
            "player_id": self.player_id,
            "prompt": self.prompt,
            "options": [o.to_dict() if isinstance(o, DecisionOption) else o for o in self.options],
            "split_count": self.split_count,
            "timeout_seconds": self.timeout_seconds,
            "negotiation_round": self.negotiation_round,
        }


@dataclass
class SettlementStepResult:
    """引擎每步结算的返回结果。

    告知 service 层下一步该做什么。
    """
    action: str = STEP_ACTION_WAITING        # show_phase / request_decision / layer_complete / round_complete / game_over
    phase: str = ""                          # 当前顶层阶段
    sub_phase: str = ""                      # 当前子阶段（可空）
    current_speed_layer: int = 0             # 当前速度层
    decision_requests: list = field(default_factory=list)  # DecisionRequest 列表（多个玩家同时决策时）
    progress_data: dict = field(default_factory=dict)      # 前端展示数据

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "phase": self.phase,
            "sub_phase": self.sub_phase,
            "current_speed_layer": self.current_speed_layer,
            "decision_requests": [
                r.to_dict() if isinstance(r, DecisionRequest) else r
                for r in self.decision_requests
            ],
            "progress_data": self.progress_data,
        }


@dataclass
class RoundSummary:
    """回合总结数据。"""
    round_num: int = 0
    pre_snapshots: dict = field(default_factory=dict)     # {player_id: resource_dict}
    post_snapshots: dict = field(default_factory=dict)    # {player_id: resource_dict}
    deaths: list = field(default_factory=list)            # 本回合死亡列表
    alive_count: int = 0
    winner: str | None = None
    game_ended: bool = False
    rank_updates: dict = field(default_factory=dict)      # {player_id: rank}
    events_summary: dict = field(default_factory=dict)    # 事件摘要（按速度层归类）

    def to_dict(self) -> dict:
        return {
            "round_num": self.round_num,
            "pre_snapshots": self.pre_snapshots,
            "post_snapshots": self.post_snapshots,
            "deaths": self.deaths,
            "alive_count": self.alive_count,
            "winner": self.winner,
            "game_ended": self.game_ended,
            "rank_updates": self.rank_updates,
            "events_summary": self.events_summary,
        }


# ═══════════════════════════════════════════════════════════════
# 对局总状态
# ═══════════════════════════════════════════════════════════════

@dataclass
class GameStateV2:
    """2.0 多人对局状态。

    替代 GameState.p1/p2 → players: list[PlayerStateV2]。
    包含状态机所需的全部上下文。
    """

    # ── 玩家 ──
    players: list[PlayerStateV2] = field(default_factory=list)

    # ── 回合 ──
    round_num: int = 0

    # ── 阶段机 ──
    phase: str = PHASE_WAITING_MOVES
    sub_phase: str = ""                     # 结算流程内的细分阶段（如 layer_targeting, layer_negotiation）

    # ── 当前速度层（仅在 phase == "speed_layer" 时有效） ──
    current_speed_layer: int = 0
    speed_layer_players: list[str] = field(default_factory=list)  # 本层涉及 player_id

    # ── 速度层循环游标 ──
    _speed_layer_cursor: int = 0            # 当前遍历到的速度层索引（0-based，对应 SPEED_LAYERS_ORDERED）

    # ── 运行时结算数据（每回合/每层重置，不持久化） ──
    target_declarations: dict[str, TargetDeclaration] = field(default_factory=dict)
    pending_decisions: dict[str, str] = field(default_factory=dict)  # {player_id: decision_type}
    current_decision_requests: list = field(default_factory=list)    # list[DecisionRequest] 当前等待的决策
    current_conflicts: list[ConflictRecord] = field(default_factory=list)
    three_chain_result: ThreeChainResult = field(default_factory=ThreeChainResult)
    random_seeds_used: list[dict] = field(default_factory=list)

    # ── 决策追踪（用于超时和去重） ──
    decision_deadline: float = 0.0              # 等待决策的截止时间戳（time.time() + timeout）
    decision_submitted_by: list[str] = field(default_factory=list)  # 已提交决策的 player_id 列表

    # ── 协商状态 ──
    negotiation_round: int = 0              # 当前协商轮次（0 = 未在协商）
    negotiation_layer: int = 0              # 正在协商的速度层
    negotiation_declarations: dict = field(default_factory=dict)  # 协商中的目标声明（序列化备份）

    # ── 胜负 ──
    winner: str | None = None              # 获胜者 player_id（"" = 平局，None = 未结束）

    # ── 历史 ──
    history: list[RoundLogV2] = field(default_factory=list)

    # ── 对局元数据 ──
    rule_version: str = "2.0"
    max_players: int = 6
    battle_id: str | None = None

    # ═══════════════════════════════════════════════════════
    # 快捷访问
    # ═══════════════════════════════════════════════════════

    def alive_players(self) -> list[PlayerStateV2]:
        return [p for p in self.players if p.is_alive()]

    def unresolved_players(self) -> list[PlayerStateV2]:
        return [p for p in self.players if p.is_alive() and p.is_unresolved() and not p.is_flashed]

    def resolved_players(self) -> list[PlayerStateV2]:
        return [p for p in self.players if p.is_resolved()]

    def dead_players(self) -> list[PlayerStateV2]:
        return [p for p in self.players if p.is_dead()]

    def get_player(self, player_id: str) -> PlayerStateV2 | None:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def all_moves_submitted(self) -> bool:
        alive = self.alive_players()
        return all(p.move_submitted for p in alive) and len(alive) > 0

    def is_game_over(self) -> bool:
        return self.winner is not None

    @property
    def alive_count(self) -> int:
        return len(self.alive_players())

    # ═══════════════════════════════════════════════════════
    # 回合生命周期
    # ═══════════════════════════════════════════════════════

    def start_round(self) -> None:
        """开始新回合：重置所有存活玩家的运行时字段。"""
        self.round_num += 1
        self.phase = PHASE_WAITING_MOVES
        self.sub_phase = ""
        self.current_speed_layer = 0
        self.speed_layer_players = []
        self._speed_layer_cursor = 0
        self.target_declarations = {}
        self.pending_decisions = {}
        self.current_decision_requests = []
        self.current_conflicts = []
        self.three_chain_result = ThreeChainResult()
        self.random_seeds_used = []
        self.negotiation_round = 0
        self.negotiation_layer = 0
        self.negotiation_declarations = {}
        self.decision_deadline = 0.0
        self.decision_submitted_by = []

        for p in self.alive_players():
            p.reset_round_runtime()

    def assign_ranks(self) -> None:
        """游戏结束时分配名次。

        按死亡回合 → 同回合死亡并列。
        存活到最后的玩家为第 1 名。
        """
        alive = self.alive_players()
        dead = self.dead_players()

        # 存活者排名从 1 开始
        for i, p in enumerate(alive):
            p.final_rank = i + 1

        # 死亡者按死亡回合分组
        by_round: dict[int, list[PlayerStateV2]] = {}
        for p in dead:
            r = p.death_round if p.death_round is not None else self.round_num
            by_round.setdefault(r, []).append(p)

        # 后死亡的排名靠前（死亡回合越大 → 存活越久 → 名次越小）
        current_rank = len(alive) + 1
        for death_round in sorted(by_round.keys(), reverse=True):
            group = by_round[death_round]
            for p in group:
                p.final_rank = current_rank
            current_rank += len(group)

    # ═══════════════════════════════════════════════════════
    # 序列化
    # ═══════════════════════════════════════════════════════

    def to_dict(self, include_history: bool = True) -> dict:
        data = {
            "round_num": self.round_num,
            "phase": self.phase,
            "sub_phase": self.sub_phase,
            "winner": self.winner,
            "rule_version": self.rule_version,
            "max_players": self.max_players,
            "battle_id": self.battle_id,
            "players": [p.to_dict() for p in self.players],
            "current_speed_layer": self.current_speed_layer,
            "speed_layer_players": self.speed_layer_players,
            "_speed_layer_cursor": self._speed_layer_cursor,
            "target_declarations": {
                player_id: declaration.to_dict()
                for player_id, declaration in self.target_declarations.items()
            },
            "pending_decisions": self.pending_decisions,
            "current_decision_requests": [
                r.to_dict() if hasattr(r, 'to_dict') else r
                for r in self.current_decision_requests
            ],
            "current_conflicts": [conflict.to_dict() for conflict in self.current_conflicts],
            "three_chain_result": self.three_chain_result.to_dict(),
            "random_seeds_used": self.random_seeds_used,
            "negotiation_round": self.negotiation_round,
            "negotiation_layer": self.negotiation_layer,
            "negotiation_declarations": self.negotiation_declarations,
        }
        if include_history:
            data["history"] = [log.to_dict() for log in self.history]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "GameStateV2":
        players_data = data.get("players", [])
        players = [PlayerStateV2.from_dict(pd) for pd in players_data]

        history_data = data.get("history", [])
        history = []
        for item in history_data:
            try:
                history.append(RoundLogV2.from_dict(item))
            except Exception:
                continue

        target_declarations = {
            player_id: TargetDeclaration.from_dict(item)
            for player_id, item in data.get("target_declarations", {}).items()
        }
        current_conflicts = [
            ConflictRecord.from_dict(item)
            for item in data.get("current_conflicts", [])
        ]

        return cls(
            players=players,
            round_num=data.get("round_num", 0),
            phase=data.get("phase", PHASE_WAITING_MOVES),
            sub_phase=data.get("sub_phase", ""),
            current_speed_layer=data.get("current_speed_layer", 0),
            speed_layer_players=data.get("speed_layer_players", []),
            _speed_layer_cursor=data.get("_speed_layer_cursor", 0),
            target_declarations=target_declarations,
            pending_decisions=data.get("pending_decisions", {}),
            current_decision_requests=data.get("current_decision_requests", []),
            current_conflicts=current_conflicts,
            three_chain_result=ThreeChainResult.from_dict(data.get("three_chain_result", {})),
            random_seeds_used=data.get("random_seeds_used", []),
            negotiation_round=data.get("negotiation_round", 0),
            negotiation_layer=data.get("negotiation_layer", 0),
            negotiation_declarations=data.get("negotiation_declarations", {}),
            winner=data.get("winner"),
            rule_version=data.get("rule_version", "2.0"),
            max_players=data.get("max_players", 6),
            battle_id=data.get("battle_id"),
            history=history,
        )
