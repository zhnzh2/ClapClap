# Step10 上线前护栏 & 灰度上线方案

## 一、上线前检查清单

### 1.1 自动化检查

```bash
# 一键检查
python -m pytest --tb=short                    # 全部 191 tests（含新增）
python scripts/validate_data.py --strict --summary  # 数据兼容校验
python -m compileall server app                # Python 编译
node --check server/static/js/pages/*.js       # 前端 JS 语法
```

### 1.2 数据兼容检查

- [ ] `scripts/validate_data.py` 通过（battles / rooms / user_indexes）
- [ ] `scripts/migrate_battles.py` 干跑无异常
- [ ] 手工检查 `data/battles/` 下是否有无法解析的 JSON
- [ ] 确认旧 1.0 记录仍能正常打开（`/record/<id>`）

### 1.3 功能冒烟

- [ ] 1.0 本地对战：正常出招、结算、存记录
- [ ] 1.0 房间对战：创建、加入、对战、回放
- [ ] 2.0 本地对战：多人出招、结算、回放页面正常
- [ ] 2.0 房间对战：创建/加入/开始/出招/结算/终局
- [ ] 2.0 回放页：`/v2/record/<id>` 正常加载
- [ ] 用户主页：1.0/2.0 战绩统计正确
- [ ] 访客登录：正常创建、可对战
- [ ] 注册/登录：正常
- [ ] 注销：对战记录标记、rub/ 迁移

### 1.4 运行环境检查

- [ ] `OPENROUTER_API_KEY` 环境变量已设置（若用 AI 功能）
- [ ] `DATA_DIR` 环境变量指向持久化 Volume（Railway 部署）
- [ ] `BACKUP_GITHUB_TOKEN` + `BACKUP_GITHUB_REPO`（可选备份）
- [ ] `EXPORT_TOKEN`（可选数据导出）
- [ ] 数据库文件 `data/clapclap.db` 可读写
- [ ] `data/battles/` 目录存在且可写
- [ ] `data/users/` 目录存在且可写

---

## 二、分批灰度上线方案

### 第一批：内部验证（1-2 天）

**范围**：你自己 + 1-2 个可信朋友
**目标**：验证核心流程无崩溃

- [ ] 使用现有生产环境（clapclap.club）或本地
- [ ] 跑完 1.3 功能冒烟全部项目
- [ ] 跑 `scripts/migrate_battles.py --apply` 修复旧数据
- [ ] 验证 Chrome / Edge / Firefox 均可正常使用
- [ ] 监控 Flask 日志无异常 traceback
- [ ] 收集团队反馈，修复致命 bug

### 第二批：公开房间测试（3-5 天）

**范围**：公告给社区（Discord / 微信群），10-30 人
**目标**：验证多人并发、真实网络条件

- [ ] 公告上线，附使用说明
- [ ] 至少完成 20+ 场 2.0 房间对战
- [ ] 至少完成 10+ 场 2.0 本地对战
- [ ] 检查回放页面无报错
- [ ] 监控并发场景：多人同时出招、同时加入
- [ ] 监控断线重连行为
- [ ] 收集所有报错日志，修复

### 第三批：全量开放（第二批后 1 周）

**范围**：不限制，开放匹配系统
**目标**：验证系统稳定性

- [ ] 启用 2.0 自动匹配功能
- [ ] 监控匹配队列去重、超时清理
- [ ] 监控房间过期自动清理
- [ ] 压测：至少 50 并发玩家（可选）
- [ ] 持续监控 1 周无 P0/P1 故障

---

## 三、回滚方案

### 如果 2.0 出问题

1. **前端入口降级**：修改 `v2/home.html`，把 2.0 入口卡片标回"维护中"
2. **路由降级**：注释 `v2_page_routes.py` 中的 2.0 路由
3. **数据不受影响**：1.0 和 2.0 数据完全独立，互不干扰

### 如果数据库损坏

1. 从 GitHub Backup 恢复 `data/`（如果配置了 BACKUP_GITHUB_TOKEN）
2. 或从 Railway Volume 快照恢复
3. 手工运行 `scripts/migrate_battles.py` 修复 JSON 记录

### 如果旧数据不兼容

1. 运行 `scripts/validate_data.py` 定位问题
2. 运行 `scripts/migrate_battles.py --apply` 批量修复
3. 对无法自动修复的记录，手工修改 JSON

---

## 四、压测 / 防刷 / 限流（后续）

当前暂未实现，建议后续补充：

- [ ] Flask 请求频率限制（Flask-Limiter）
- [ ] Socket.IO 消息频率限制
- [ ] 匹配队列去重（已有） + 限流
- [ ] 房间创建频率限制
- [ ] 文件上传大小限制
- [ ] SQLite 连接池 / WAL 模式优化
- [ ] 使用 locust 或 wrk 做压测

---

## 五、已部署的功能验证矩阵

| 功能 | 1.0 | 2.0 | 测试覆盖 |
|------|-----|-----|----------|
| 本地对战 | ✅ | ✅ | test_local.py |
| 房间创建/加入 | ✅ | ✅ | test_room.py, test_room_v2.py |
| 出招/结算 | ✅ | ✅ | test_game_v2.py, test_logic.py |
| 匹配系统 | ✅ | ✅ | test_match.py, test_match_v2.py |
| 观战 | ✅ | ✅ | e2e test |
| 回放页面 | ✅ | ✅ | test_replay_consistency.py |
| 用户主页/战绩 | ✅ | ✅ | test_user_features.py |
| 对战记录存档 | ✅ | ✅ | test_replay_consistency.py |
| 注销/rub迁移 | ✅ | ✅ | test_user_features.py |
| 并发安全 | — | ✅ | test_concurrent_v2.py |
| 重连/心跳 | — | ✅ | test_concurrent_v2.py |
| 数据验证器 | ✅ | ✅ | validate_data.py |
| 记录迁移器 | — | ✅ | migrate_battles.py |
