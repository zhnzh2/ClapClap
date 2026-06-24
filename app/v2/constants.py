"""
ClapClap 2.0 多人版常量定义。

与 1.0 (app/constants.py) 共享 Move 枚举和基础资源类型。
本文件仅定义 2.0 新增的常量。
"""

from __future__ import annotations

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

# ── 游戏阶段枚举 ──────────────────────────────────────────

PHASE_WAITING_MOVES = "waiting_moves"      # 等待所有玩家提交动作
PHASE_RESOURCE_CHECK = "resource_check"    # 资源合法性检查
PHASE_REVEAL = "reveal"                    # 统一亮招
PHASE_FLASH = "flash"                      # 闪结算
PHASE_THREE_CHAIN = "three_chain"          # 三连检测与结算
PHASE_SPEED_LAYER = "speed_layer"          # 速度层循环
PHASE_DEATH_CHECK = "death_check"          # 死亡与胜负判定
PHASE_FINISHED = "finished"                # 对局结束
