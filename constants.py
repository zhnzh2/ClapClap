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