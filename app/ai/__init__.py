# ClapClap 1.0 AI 模块
#
# 本包包含：
#   space.py   - 动作空间注册表（action_index <-> Move 双向映射、空间指纹）
#   engine.py  - 合法动作掩码、玩家视角转换、统一策略接口
#
# AI 不重新实现规则，只调用现有 app/v1/ 下的规则引擎。
