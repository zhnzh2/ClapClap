"""
ClapClap 1.0 AI 动作空间注册表。

从 Move 枚举自动生成，不在 AI 模块中手写第二份动作表。
提供：
  - action_index <-> Move 双向映射
  - 动作空间指纹（用于未来模型加载时校验）
"""

from __future__ import annotations

import hashlib
from typing import Dict, Final, List

from app.v1.constants import Move

# ---------------------------------------------------------------------------
# 动作空间
# ---------------------------------------------------------------------------

# 从 Move 枚举自动生成，顺序与枚举定义顺序一致
_MOVES_IN_ORDER: Final[List[Move]] = list(Move)

ACTION_SPACE_SIZE: Final[int] = len(_MOVES_IN_ORDER)  # 应为 17

# action_index (int) -> Move
MOVE_BY_INDEX: Final[Dict[int, Move]] = {
    i: move for i, move in enumerate(_MOVES_IN_ORDER)
}

# Move -> action_index (int)
INDEX_BY_MOVE: Final[Dict[Move, int]] = {
    move: i for i, move in enumerate(_MOVES_IN_ORDER)
}


# ---------------------------------------------------------------------------
# 动作空间指纹
# ---------------------------------------------------------------------------

def _compute_fingerprint() -> str:
    """基于 17 个动作名和顺序计算 SHA-256 指纹。"""
    names = "|".join(move.name for move in _MOVES_IN_ORDER)
    return hashlib.sha256(names.encode("utf-8")).hexdigest()


ACTION_SPACE_FINGERPRINT: Final[str] = _compute_fingerprint()


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def get_move_by_index(index: int) -> Move:
    """action_index -> Move。"""
    if index < 0 or index >= ACTION_SPACE_SIZE:
        raise IndexError(f"动作索引 {index} 超出范围 [0, {ACTION_SPACE_SIZE})")
    return MOVE_BY_INDEX[index]


def get_index_by_move(move: Move) -> int:
    """Move -> action_index。"""
    return INDEX_BY_MOVE[move]


def get_action_space_fingerprint() -> str:
    """返回当前动作空间指纹（SHA-256 十六进制字符串）。"""
    return ACTION_SPACE_FINGERPRINT


def get_moves_in_order() -> List[Move]:
    """返回按枚举顺序排列的动作列表（只读副本）。"""
    return list(_MOVES_IN_ORDER)


def validate_action_space(space_size: int, fingerprint: str) -> bool:
    """
    校验外部传入的动作空间是否与当前一致。

    如果动作数量或顺序发生变化，旧模型必须拒绝加载。
    """
    return space_size == ACTION_SPACE_SIZE and fingerprint == ACTION_SPACE_FINGERPRINT
