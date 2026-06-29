from __future__ import annotations

from enum import Enum
from typing import Dict, Final


class Resource(str, Enum):
    HP = "hp"
    QI = "qi"
    SHIELD = "shield"
    SPARK = "spark"
    BATTERY = "battery"
    PICKAXE = "pickaxe"


class Move(str, Enum):
    # 资源
    QI = "气"
    SHIELD = "盾"

    # 气系攻击
    GI = "gi"
    PO = "破"
    LENG_FENG = "冷锋"
    RU_LAI = "如来"
    HEI_DONG = "黑洞"

    # 盾系攻击
    FIRE = "Fire"
    SHAN_DIAN = "闪电"
    LIE_YAN = "烈焰"
    SHINING = "Shining"

    # 防御
    SHI_ZI = "十字"
    BA_GUA = "八卦"

    # 锦囊
    CHI = "你吃"
    SHUANG_CHI = "双吃"
    SHAN = "闪"
    GAO = "镐"


# -------------------------
# 初始值
# -------------------------

INITIAL_HP: Final[int] = 1
INITIAL_QI: Final[int] = 0
INITIAL_SHIELD: Final[int] = 0
INITIAL_SPARK: Final[int] = 0
INITIAL_BATTERY: Final[int] = 0
INITIAL_PICKAXE: Final[int] = 0

MAX_FLASH_USE: Final[int] = 2


# -------------------------
# 动作消耗
# 这里只写“固定消耗”
# 像 烈焰 / Shining 这种可替代消耗，先不写死在这里
# 后面在 game.py 里专门处理
# -------------------------

MOVE_COSTS: Final[Dict[Move, Dict[Resource, int]]] = {
    Move.QI: {},
    Move.SHIELD: {},

    Move.GI: {Resource.QI: 1},
    Move.PO: {Resource.QI: 2},
    Move.LENG_FENG: {Resource.QI: 3},
    Move.RU_LAI: {Resource.QI: 5},
    Move.HEI_DONG: {Resource.QI: 8},

    Move.FIRE: {Resource.SHIELD: 2},
    Move.SHAN_DIAN: {Resource.SHIELD: 3},

    # 特殊处理：优先火种 / 优先电池
    Move.LIE_YAN: {},
    Move.SHINING: {},

    Move.SHI_ZI: {Resource.QI: 2},
    Move.BA_GUA: {Resource.QI: 3},

    Move.CHI: {Resource.QI: 1},
    Move.SHUANG_CHI: {Resource.QI: 2},
    Move.SHAN: {},
    Move.GAO: {Resource.QI: 2},
}


# -------------------------
# 攻击力
# 非攻击动作不在这里写
# -------------------------

ATTACK_POWER: Final[Dict[Move, float]] = {
    Move.GI: 1.0,
    Move.PO: 2.0,
    Move.LENG_FENG: 3.0,
    Move.RU_LAI: 4.0,
    Move.HEI_DONG: 5.0,

    Move.FIRE: 1.5,
    Move.SHAN_DIAN: 2.0,
    Move.LIE_YAN: 3.0,
    Move.SHINING: 4.0,
}


# -------------------------
# 防御力
# 攻击手势的防御力 = 其攻击力
# 资源、防御、锦囊动作单独列
# -------------------------

DEFENSE_POWER: Final[Dict[Move, float]] = {
    Move.QI: 0.0,
    Move.SHIELD: 1.5,

    Move.GI: 1.0,
    Move.PO: 2.0,
    Move.LENG_FENG: 3.0,
    Move.RU_LAI: 4.0,
    Move.HEI_DONG: 5.0,

    Move.FIRE: 1.5,
    Move.SHAN_DIAN: 2.0,
    Move.LIE_YAN: 3.0,
    Move.SHINING: 4.0,

    Move.SHI_ZI: 3.0,
    Move.BA_GUA: 4.0,

    # 吃/双吃默认未命中时视为 0
    # 真正是否命中、是否特殊抵消，后面在 game.py 里判
    Move.CHI: 0.0,
    Move.SHUANG_CHI: 0.0,

    # 闪不参与本回合结算，严格说这里不会用到
    Move.SHAN: 0.0,
    Move.GAO: 0.0,
}


# -------------------------
# 伤害值
# 普通攻击 1 点，如来/Shining 2 点，黑洞 3 点
# 第一版先不拆分
# -------------------------

DAMAGE_VALUE: Final[Dict[Move, int]] = {
    Move.GI: 1,
    Move.PO: 1,
    Move.LENG_FENG: 1,
    Move.RU_LAI: 2,
    Move.HEI_DONG: 3,

    Move.FIRE: 1,
    Move.SHAN_DIAN: 1,
    Move.LIE_YAN: 1,
    Move.SHINING: 2,
}


# -------------------------
# 动作分类
# -------------------------

RESOURCE_MOVES: Final[set[Move]] = {
    Move.QI,
    Move.SHIELD,
}

ATTACK_MOVES: Final[set[Move]] = {
    Move.GI,
    Move.PO,
    Move.LENG_FENG,
    Move.RU_LAI,
    Move.HEI_DONG,
    Move.FIRE,
    Move.SHAN_DIAN,
    Move.LIE_YAN,
    Move.SHINING,
}

DEFENSE_MOVES: Final[set[Move]] = {
    Move.SHI_ZI,
    Move.BA_GUA,
}

TRICK_MOVES: Final[set[Move]] = {
    Move.CHI,
    Move.SHUANG_CHI,
    Move.SHAN,
    Move.GAO,
}


# -------------------------
# 特殊关系表
# 第一版双吃不拆分，只按整体动作处理
# -------------------------

CHI_TARGETS: Final[set[Move]] = {
    Move.PO,
    Move.SHAN_DIAN,
}

SHUANG_CHI_TARGETS: Final[set[Move]] = {
    Move.PO,
    Move.SHAN_DIAN,
    Move.SHINING,
}

# -------------------------
# 2.0-specific constants
# -------------------------

# ── 房间参数 ──────────────────────────────────────────────

# 人数限制（来自阶段 1 规则定稿）
MIN_PLAYERS = 2
MAX_PLAYERS = 6

# ── 速度层定义 ────────────────────────────────────────────

# 速度层枚举（按结算先后，值越小越快）
SPEED_LAYER_FLASH = 1          # 闪
SPEED_LAYER_THREE_CHAIN = 2    # 三连
SPEED_LAYER_CHI_SHUANGCHI = 3  # 你吃 / 双吃
SPEED_LAYER_GI_VS_HEIDONG = 4  # gi 攻击黑洞
SPEED_LAYER_HEIDONG = 5        # 黑洞
SPEED_LAYER_RULAI_SHINING = 6  # 如来 / Shining
SPEED_LAYER_LENGFENG_LIEYAN = 7  # 冷锋 / 烈焰
SPEED_LAYER_GI_ATTACK_STEAL = 8  # gi 造成伤害 / gi 抢镐
SPEED_LAYER_PO_SHANDIAN = 9    # 破 / 闪电
SPEED_LAYER_FIRE = 10          # Fire
SPEED_LAYER_GI_NO_TARGET = 11  # 无合法目标的 gi
SPEED_LAYER_RESOURCES = 12     # 气 / 盾 / 加镐

# 速度层 → 名称映射
SPEED_LAYER_NAMES = {
    SPEED_LAYER_FLASH: "闪",
    SPEED_LAYER_THREE_CHAIN: "三连",
    SPEED_LAYER_CHI_SHUANGCHI: "你吃/双吃",
    SPEED_LAYER_GI_VS_HEIDONG: "gi 攻击黑洞",
    SPEED_LAYER_HEIDONG: "黑洞",
    SPEED_LAYER_RULAI_SHINING: "如来/Shining",
    SPEED_LAYER_LENGFENG_LIEYAN: "冷锋/烈焰",
    SPEED_LAYER_GI_ATTACK_STEAL: "gi 攻击/抢镐",
    SPEED_LAYER_PO_SHANDIAN: "破/闪电",
    SPEED_LAYER_FIRE: "Fire",
    SPEED_LAYER_GI_NO_TARGET: "gi 无目标",
    SPEED_LAYER_RESOURCES: "气/盾/加镐",
}

# 按速度顺序排列的层级列表（除闪和三连在循环之前单独处理）
SPEED_LAYERS_ORDERED = list(range(SPEED_LAYER_CHI_SHUANGCHI, SPEED_LAYER_RESOURCES + 1))

# ── 玩家状态枚举 ──────────────────────────────────────────

# 玩家在对局中的状态
PLAYER_ALIVE = "alive"            # 存活中
PLAYER_DEAD = "dead"              # 死亡
PLAYER_SPECTATING = "spectating"  # 观战

# 结算中的玩家状态
PLAYER_UNRESOLVED = "unresolved"  # 未操作对象
PLAYER_RESOLVED = "resolved"      # 已操作对象

# ── 死亡原因 ──────────────────────────────────────────────

DEATH_NORMAL = "normal"         # 生命值 ≤ 0（回合末）
DEATH_BOOM_PICKAXE = "boom"     # 爆镐（立即）
DEATH_BOOM_RESOURCE = "ant"     # 爆气/爆盾（阶段 A 立即）
DEATH_SLOW = "toad"             # 蛤蟆（慢出手，立即）
DEATH_ILLEGAL = "fake_toad"     # 蟆蛤（不合规手势，立即）
DEATH_SURRENDER = "surrender"   # 投降/断线（房间层面）

# ── 协商参数 ──────────────────────────────────────────────

NEGOTIATION_MAX_ROUNDS = 3       # 协商最大轮数
NEGOTIATION_TIMEOUT_SEC = 30     # 每轮协商限时秒数（暂未启用）

# ── 三连类型 ──────────────────────────────────────────────

THREE_CHAIN_TYPE_GI_CHI_PO = "gi_chi_po"            # gi — 你吃/双吃 — 破
THREE_CHAIN_TYPE_GI_HEIDONG_OTHER = "gi_heidong_other"  # gi — 黑洞 — 其它攻击

# ── 游戏阶段枚举（顶层，6 个主要阶段）──────────────────────

PHASE_WAITING_MOVES = "waiting_moves"      # 等待所有玩家提交动作
PHASE_RESOURCE_CHECK = "resource_check"    # 资源合法性检查
PHASE_REVEAL = "reveal"                    # 统一亮招
PHASE_FLASH = "flash"                      # 闪结算
PHASE_THREE_CHAIN = "three_chain"          # 三连检测与结算
PHASE_SPEED_LAYER = "speed_layer"          # 速度层循环
PHASE_DEATH_CHECK = "death_check"          # 死亡与胜负判定
PHASE_ROUND_SUMMARY = "round_summary"      # 回合总结
PHASE_FINISHED = "finished"                # 对局结束

# ── 游戏子阶段枚举（结算流程内的细分状态）──────────────────

# 三连子阶段
SUB_PHASE_THREE_CHAIN_DETECT = "three_chain_detect"      # 三连检测中
SUB_PHASE_THREE_CHAIN_SELECT = "three_chain_select"       # 等待三连人选选择
SUB_PHASE_THREE_CHAIN_RESOLVE = "three_chain_resolve"     # 三连结算中

# 速度层子阶段
SUB_PHASE_LAYER_TARGETING = "layer_targeting"              # 等待玩家选择目标
SUB_PHASE_LAYER_INTENT_REVEAL = "layer_intent_reveal"      # 同速意向公开
SUB_PHASE_LAYER_NEGOTIATION = "layer_negotiation"          # 冲突协商中
SUB_PHASE_LAYER_EXECUTION = "layer_execution"              # 执行速度层结算
SUB_PHASE_LAYER_RESULT = "layer_result"                    # 速度层结算结果展示

# ── 决策类型常量 ──────────────────────────────────────────

DECISION_TYPE_TARGET_SELECT = "target_select"              # 选择攻击/锦囊目标
DECISION_TYPE_THREE_CHAIN_SELECT = "three_chain_select"    # 三连人选选择
DECISION_TYPE_CONFLICT_RESOLVE = "conflict_resolve"        # 冲突协商

# ── 结算步进动作 ──────────────────────────────────────────

STEP_ACTION_SHOW_PHASE = "show_phase"          # 展示阶段结果（前端展示）
STEP_ACTION_REQUEST_DECISION = "request_decision"  # 请求玩家决策
STEP_ACTION_LAYER_COMPLETE = "layer_complete"  # 速度层完成
STEP_ACTION_ROUND_COMPLETE = "round_complete"  # 回合完成
STEP_ACTION_GAME_OVER = "game_over"            # 对局结束
STEP_ACTION_WAITING = "waiting"                # 等待中（无新动作）

# 阶段展示名称
PHASE_DISPLAY_NAMES = {
    PHASE_WAITING_MOVES: "等待出招",
    PHASE_RESOURCE_CHECK: "资源检查",
    PHASE_REVEAL: "统一亮招",
    PHASE_FLASH: "闪结算",
    PHASE_THREE_CHAIN: "三连检测",
    PHASE_SPEED_LAYER: "速度层结算",
    PHASE_DEATH_CHECK: "死亡判定",
    PHASE_ROUND_SUMMARY: "回合总结",
    PHASE_FINISHED: "对局结束",
}
