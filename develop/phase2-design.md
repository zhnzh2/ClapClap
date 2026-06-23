# 阶段 2 设计文档：规则版本体系

> 定稿 2026-06-23

## 原则

- **不动 1.0 逻辑**：`app/game.py`、现有结算流程、现有数据模型的行为完全不变
- **最小必需字段**：只在 Room 加一个 `rule_version` 默认值字段，旧数据自动兼容
- **2.0 独立**：新建 `app/game_v2.py`，所有 2.0 结构独立定义

## 2.1 版本标识

### Room 数据模型（`app/room_manager.py`）

```python
@dataclass
class Room:
    # ... 现有字段不变 ...
    rule_version: str = "1.0"   # 新增。默认 "1.0" 保证旧数据兼容
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `rule_version` | `str` | `"1.0"` | 旧房间/旧数据无此字段时自动取 "1.0" |

### 对局记录（`app/battle_recorder.py`）

battle JSON 新增 `rule_version` 字段：

```json
{
  "battle_id": "...",
  "rule_version": "1.0",
  "participants": { ... },
  "rounds": [ ... ]
}
```

### 向前兼容规则

- 旧 JSON 无 `rule_version` → 读取时默认 `"1.0"`
- 未知版本号 → 明确报错，不猜测

## 2.2 引擎分发

### 引擎入口

```
server/services/room_service.py
  └── submit_room_move_service()
        └── if room.rule_version == "1.0":
              GameEngine.resolve_round(...)      # 现有引擎
            elif room.rule_version == "2.0":
              GameEngineV2.resolve_round(...)    # 新建引擎（当前为骨架）
            else:
              raise UnknownRuleVersion(...)
```

### 文件结构

```
app/
├── game.py          # 1.0 引擎（不动）
├── game_v2.py       # 2.0 引擎（新建，阶段 4 实现）
├── models.py        # 1.0 模型（不动）
├── models_v2.py     # 2.0 模型（新建，阶段 3 实现）
├── constants.py     # 共享常量（不动）
├── constants_v2.py  # 2.0 新增常量（新建）
```

## 2.3 兼容性

### 旧房间恢复

- `Room.from_dict()` 检测 `rule_version` 字段
- 不存在 → 默认 `"1.0"` → 走 1.0 引擎
- 旧房间的结算行为完全不变

### 旧 JSON 对局记录

- `load_battle()` 读取后检查 `rule_version`
- 不存在 → 补充为 `"1.0"`
- 旧回放页面读取旧记录不报错

### 未知版本

- 若 room.rule_version 不是 "1.0" 或 "2.0" → 抛出异常
- 前端显示明确错误信息

### 新旧数据分离

- 1.0 房间和 2.0 房间使用同一 SQLite 表（room_store），通过 `rule_version` 字段区分
- 1.0 对局和 2.0 对局使用同一 battles/ 目录，通过 JSON 内 rule_version 字段区分

## 变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/room_manager.py` | 修改 | Room 加 rule_version 字段 + to_dict/from_dict |
| `app/battle_recorder.py` | 修改 | create_battle 接受 rule_version |
| `app/state_api.py` | 修改 | get_room_payload 透出 rule_version |
| `app/game_v2.py` | **新建** | 2.0 引擎骨架 |
| `app/constants_v2.py` | **新建** | 2.0 常量（速度层、人数限制等） |
| `server/services/room_service.py` | 修改 | 引擎分发 + 创建房间传 rule_version |
| `server/routes/room_routes.py` | 修改 | POST /api/rooms 接受 rule_version 参数 |
