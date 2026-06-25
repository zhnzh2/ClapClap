# ClapClap 👏

**拍拍** —— 同步出招手势对战网页游戏。从 1.0 双人对战到 2.0 多人速度层结算，规则深度不断提升。

> 🎯 项目状态：**1.0 双人版稳定运行，2.0 多人版规则引擎 + 本地模拟 + 多人房间前端已完成（Step1~7），当前准备进入 Step8。**
>
> 已将 ClapClap 从一套原创规则，推进成为一个支持双版本引擎、可联机、可匹配、带用户系统、对战存档和实时聊天的完整网页游戏平台。

---

## 🎮 游戏简介

### 1.0 双人版（稳定）

回合制双人对战。每回合双方同时选择一个动作，由规则引擎统一结算。18 种动作分为四大类：

| 类别 | 动作 | 说明 |
|------|------|------|
| **资源** | 气、盾 | 获得基础资源 |
| **攻击（气系）** | gi、破、冷锋、如来、黑洞 | 气系攻击，攻防数值递增 |
| **攻击（盾系）** | Fire、闪电、烈焰、Shining | 盾系攻击，产生派生资源 |
| **防御** | 十字防、八卦 | 高防御力抵挡攻击 |
| **锦囊** | 你吃、双吃、闪、镐 | 特殊策略：克制、闪避、回血 |

### 2.0 多人版（开发中）

从双人对战升级为 **最多 6 人同时竞技**。核心新增：

- **速度层结算（12 层）**——闪→三连→你吃/双吃→gi反黑洞→黑洞→如来/Shining→冷锋/烈焰→gi攻击/抢镐→破/闪电→Fire→gi无目标→气/盾/加镐
- **目标选择与协商**——同速玩家秘密选择目标 → 统一公开 → 冲突识别 → 最多 3 轮协商
- **三连机制**——gi/你吃/破 三人循环克制；gi/黑洞/任意攻击
- **分段技能**——黑洞拆 3 段、Shining 拆 2 闪电、双吃拆 2 你吃
- **已操作/未操作状态**——被攻击后变为已操作，后续速度层不可行动
- **淘汰制胜负**——最后一名存活者获胜

> 📖 完整规则书：`rules/version 1.0/rule.tex`（双人）、`rules/version 2.0/rule2.0.tex`（多人）
> 📐 数字版结算规范：`develop/rule-spec-2.0.md`

---

## ✨ 功能特性

### 👤 账号系统

| 功能 | 说明 |
|------|------|
| **注册/登录** | 用户名 + 密码 + 介绍信 |
| **访客登录** | 一键创建 `visitor_XXXXX` 账号，默认密码 ClapClap |
| **UID 分配** | 自动分配最小未使用的正整数 UID（admin 为 0） |
| **用户主页** | 查看公开资料与分页历史战绩，进入完整对局回放 |
| **账号管理** | 修改用户名/介绍信；验证当前密码后修改密码；支持注销账号 |
| **管理员** | 查看所有用户表格，验证/注销用户 |
| **自动清理** | 未验证账号超过 30 天自动注销 |
| **Session 认证** | 所有 API 自动携带 session token，未登录强制跳转 |

### 🎮 游戏模式

| 模式 | 说明 | 规则 | 状态 |
|------|------|------|------|
| **🏠 本地双人（1.0）** | 同屏操作，适合体验规则和本地测试 | 1.0 双人 | ✅ 稳定 |
| **🏠 房间对战（1.0）** | 创建/加入双人房间，好友联机 | 1.0 双人 | ✅ 稳定 |
| **🔍 自动匹配（1.0）** | 匹配队列自动配对在线玩家 | 1.0 双人 | ✅ 稳定 |
| **🎮 本地模拟（2.0）** | 一人操作所有玩家，裁判模式体验多人规则 | 2.0 多人 | ✅ 完成 |
| **🌐 多人房间（2.0）** | 创建/加入多人房间，在线速度层对战 | 2.0 多人 | ✅ 完成 |
| **👀 观战增强（2.0）** | 观战者加入、退出、视图增强、死亡后观战体验 | 2.0 多人 | 🚧 Step8 |
| **🔍 自动匹配（2.0）** | 按规则版本和目标人数组队进入多人房间 | 2.0 多人 | 🚧 Step8 |
| **💬 实时聊天** | 房间内参战/观战均可打字沟通，最多 50 字 | - | ✅ 完成 |
| **🤖 AI 对战** | 入口已预留，计划接入启发式 bot | 1.0/2.0 | 🔜 待开发 |

### 📊 数据与记录

| 功能 | 说明 |
|------|------|
| **对战记录** | 每局对战独立 JSON 存档，精确到毫秒命名 |
| **回合明细** | 每回合双方/多人动作完整记录（含速度层事件） |
| **Web 回放** | 分页展示历史战绩，可查看动作、伤害与资源快照 |
| **聊天存档** | 聊天记录与时间戳同步写入对局文件 |
| **用户索引** | 每个用户文件夹下记录参与过的所有对局 |
| **注销标记** | 用户注销后标记关联对局，全员注销移入 rub/ |
| **数据导出** | API 一键下载 SQLite 数据库 |
| **自动备份** | 定时推送到 GitHub 私有仓库 |

### 🔧 技术特性

- **⚡ 实时同步** — Socket.IO 房间状态实时推送，WebSocket + HTTP 轮询双通道兜底
- **🔒 私密信息保护** — 未亮招动作仅自己可见，决策请求仅通过私有 Socket 频道下发
- **🧩 双引擎架构** — 1.0 和 2.0 引擎独立运行，根据房间 `rule_version` 分发
- **💾 持久化存储** — SQLite 存储房间和匹配状态，文件系统存储用户数据
- **📁 对战存档** — JSON 文件存储每局完整记录（含速度层事件序列）
- **🎨 响应式 UI** — 支持桌面和移动端，紧凑模式适配 150% 缩放，键盘快捷键
- **🔐 身份系统** — session token + player_token 双重认证
- **🗑️ 账号注销** — 不可逆删除，自动清理关联房间/匹配/对局标记
- **📋 规则版本体系** — 房间和对局记录携带 `rule_version` 字段，旧数据自动兼容

---

## 🛠 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| **后端框架** | Python / Flask | Web 应用与 RESTful API |
| **实时通信** | Flask-SocketIO | 房间状态 + 多人决策 + 聊天实时推送 |
| **前端** | 原生 JavaScript（无框架） | 页面交互与动态渲染 |
| **模板** | Jinja2 | 服务端页面渲染 |
| **存储 - 游戏** | SQLite | 房间与匹配状态持久化 |
| **存储 - 用户** | 文件系统（CSV + 文件夹） | 账号、session、对局记录 |
| **密码** | SHA-256（UID 加盐） | 密码哈希 |
| **部署** | gunicorn / Railway + Cloudflare | 生产运行与域名访问 |
| **备份** | Git + GitHub API | 定时自动备份数据库 |

### 项目架构

```
┌─────────────────────────────────────────────────────────────┐
│                 前端层 (Jinja2 + 原生 JS)                    │
│  模板页面 → Socket.IO 客户端 → localStorage 缓存           │
│  core/: ApiUtils / MessageUtils / ModalUtils / BootUtils   │
│        / SessionUtils / StorageUtils                        │
│  online/: room_identity / room_rendering / decision         │
│  pages/: 各页面控制器                                       │
│  v2 独立: v2_room_*.js / v2_rooms_*.js / v2_local*.js     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│               服务层 (Flask + SocketIO)                      │
│  HTTP Routes (pages/local/room/match/auth/status/export)   │
│  v2 Routes  (v2_page / v2_local / v2_room / v2_decision)  │
│  Socket Events v1 + v2 (join/submit/decision/chat)         │
│  Auth Middleware (require_auth decorator)                  │
│  Services (room_service.py / room_v2_service.py)           │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              核心引擎层 (app/ + app/v2/)                     │
│  1.0: GameEngine → 回合结算                                 │
│  2.0: GameEngineV2 → 速度层结算 + 目标选择 + 冲突协商       │
│  RoomManager / RoomManagerV2 → 房间生命周期                  │
│  Matchmaking → 匹配队列                                     │
│  Storage → SQLite 持久化                                    │
│  Users → 用户管理（CSV + 文件系统）                          │
│  BattleRecorder → 对战记录                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
ClapClap/
├── app/                         # 核心引擎层（1.0）
│   ├── constants.py             # 共享动作枚举、数值常量
│   ├── game.py                  # 1.0 规则引擎（双人对战）
│   ├── models.py                # 1.0 数据模型
│   ├── matchmaking.py           # 1.0 匹配队列
│   ├── room_manager.py          # 1.0 房间管理
│   ├── state_api.py             # 1.0 状态序列化
│   ├── storage.py               # SQLite 持久化
│   ├── users.py                 # 用户存储与鉴权
│   └── battle_recorder.py       # 对战记录（JSON 存档）
│
├── app/v2/                      # 核心引擎层（2.0）——全新独立实现
│   ├── constants.py             # 2.0 常量（速度层/阶段/人数限制）
│   ├── game.py                  # 2.0 规则引擎（步进式多人结算）
│   ├── models.py                # 2.0 数据模型（含 DecisionRequest/SettlementStepResult）
│   ├── room.py                  # 2.0 房间模型（SeatV2/SpectatorV2）
│   ├── room_manager.py          # 2.0 房间管理器
│   └── state_api.py             # 2.0 状态序列化（含决策请求/回合总结载荷）
│
├── server/                      # Flask 服务层
│   ├── app.py                   # 应用入口（双引擎注册）
│   ├── socket_events.py         # 1.0 WebSocket 事件
│   ├── socket_events_v2.py      # 2.0 WebSocket 事件（决策私发/结算进度/回合总结）
│   ├── auth_middleware.py        # require_auth 装饰器
│   ├── runtime.py               # 周期性清理
│   ├── backup.py                # GitHub 自动备份
│   ├── routes/                  # HTTP 路由
│   │   ├── page_routes.py       #   页面路由（/ /local /rooms /match /room/<id> /user/<id>）
│   │   ├── v2_page_routes.py    #   2.0 页面路由（/v2 /v2/local /v2/rooms /v2/room/<id>）
│   │   ├── v2_local_routes.py   #   2.0 本地模拟 API
│   │   ├── local_routes.py      #   1.0 本地模式 API
│   │   ├── room_routes.py       #   1.0 房间 API
│   │   ├── room_v2_routes.py    #   2.0 房间 API（创建/加入/决策/公开列表）
│   │   ├── match_routes.py      #   匹配 API
│   │   ├── status_routes.py     #   状态检查 API
│   │   ├── export_routes.py     #   数据库导出 API
│   │   └── auth_routes.py       #   认证 + 管理员 API
│   ├── services/                # 业务逻辑层
│   │   ├── room_service.py      #   1.0 房间服务
│   │   └── room_v2_service.py   #   2.0 房间服务（引擎连接/决策提交/对局记录）
│   ├── templates/               # Jinja2 模板
│   │   ├── login.html           #   登录/注册页
│   │   ├── home.html            #   1.0 主页（模式大厅）
│   │   ├── local.html           #   1.0 本地双人模式
│   │   ├── rooms.html           #   1.0 房间列表
│   │   ├── room_detail.html     #   1.0 房间对战详情
│   │   ├── match.html           #   匹配模式
│   │   ├── ai.html              #   AI 模式（预留）
│   │   ├── user.html            #   用户主页
│   │   ├── record.html          #   对局回放
│   │   └── v2/                  #   2.0 模板
│   │       ├── home.html        #     2.0 大厅（本地模拟 + 多人房间入口）
│   │       ├── local.html       #     2.0 本地模拟对战
│   │       ├── rooms.html       #     2.0 房间列表（创建/加入卡片 + 公开房间表格）
│   │       └── room.html        #     2.0 房间对战（玩家面板 + 动作选择 + 决策弹窗）
│   └── static/                  # 前端资源
│       ├── css/
│       │   ├── auth.css         #   登录/账号/弹窗基础样式
│       │   ├── local.css / match.css / rooms.css / room_detail*.css  # 1.0 样式
│       │   ├── v2_local.css     #   2.0 本地模拟样式
│       │   ├── v2_rooms.css     #   2.0 房间列表样式
│       │   └── v2_room.css      #   2.0 房间对战样式（含 12 层速度条/决策弹窗/聊天）
│       └── js/
│           ├── socket.io.min.js #   Socket.IO 客户端
│           ├── core/            #   共享模块（1.0/2.0 共用）
│           │   ├── api.js       #     API 请求封装（自动携带 X-Session-Token）
│           │   ├── boot.js      #     服务器重启检测与缓存清理
│           │   ├── message.js   #     消息提示组件
│           │   ├── modal.js     #     全局弹窗系统（确认/信息/成功）
│           │   ├── session.js   #     前端 session 管理
│           │   └── storage.js   #     localStorage 工具
│           ├── online/          #   联机逻辑
│           │   ├── room_state.js / room_identity.js / resume_room.js  # 1.0
│           │   ├── match_state.js / history_renderer.js               # 1.0
│           │   ├── v2_room_identity.js    #     2.0 房间身份存储
│           │   ├── v2_room_rendering.js   #     2.0 UI 渲染（玩家卡片/速度层/结算事件）
│           │   └── v2_room_decision.js    #     2.0 决策弹窗（目标选择/三连/协商）
│           └── pages/           #   页面入口
│               ├── login_page.js / home_page.js / user_page.js   # 1.0/通用
│               ├── local_page*.js / rooms_page.js / match_page.js # 1.0
│               ├── room_detail_page.js / room_detail_data.js     # 1.0
│               ├── record_page.js / account_modal.js             # 1.0/通用
│               ├── v2_local*.js              #   2.0 本地模拟
│               ├── v2_rooms_page.js          #   2.0 房间列表逻辑
│               └── v2_room_page.js           #   2.0 房间对战主控制器
│
├── data/                         # 数据目录（生产环境挂载 Volume）
│   ├── clapclap.db               # SQLite 数据库
│   ├── users/                    # 用户数据
│   │   ├── users.csv             #   用户索引
│   │   └── User_X/               #   各用户文件夹
│   └── battles/                  # 对战记录
│       └── rub/                  #   全员注销的对局
│
├── tests/                       # 单元测试
│   ├── test_logic.py            # 1.0 规则引擎测试
│   ├── test_match.py / test_room.py / test_local.py / test_status.py
│   ├── test_user_features.py
│   ├── test_game_v2.py          # 2.0 规则引擎测试（含速度层/三连/协商）
│   ├── test_models_v2.py        # 2.0 数据模型测试
│   └── test_room_v2.py          # 2.0 房间协议测试（含隐私/路由）
│
├── develop/                     # 设计文档
│   ├── rule-spec-2.0.md         # 2.0 数字版结算规范（定稿）
│   ├── phase2-design.md         # 阶段 2 设计文档（版本体系）
│   ├── rule-cases.html          # 规则判例表
│   ├── rule-flowchart.html      # 结算阶段流程图
│   └── rule-review.html         # 规则审查记录
│
├── rules/                       # LaTeX 规则文档
│   ├── version 1.0/             # 1.0 双人版规则书
│   └── version 2.0/             # 2.0 多人版规则书
│
├── requirements.txt             # Python 依赖
├── README.md                    # 本文件
├── task.txt                     # 2.0 多人化升级任务书（10 阶段）
├── history.md                   # 开发对话历史
└── CLAUDE.md                    # AI 助手项目规范
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+

### 安装运行

```bash
# 克隆仓库
git clone https://github.com/zhnzh2/ClapClap.git
cd ClapClap

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate     # Windows
# source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 启动服务（开发模式）
python server/app.py
```

打开浏览器访问 `http://127.0.0.1:5000`（1.0 大厅）或 `http://127.0.0.1:5000/v2`（2.0 大厅）。

首次启动会自动创建 admin 账号：用户名 `zhnzh`，密码 `207101`。

### 主要页面入口

| URL | 说明 |
|-----|------|
| `/` | 1.0 大厅（双人本地/房间/匹配/AI） |
| `/local` | 1.0 本地双人模拟 |
| `/rooms` | 1.0 双人房间 |
| `/room/<id>` | 1.0 双人房间对战 |
| `/match` | 1.0 自动匹配 |
| **`/v2`** | **2.0 大厅（本地模拟 + 多人房间入口）** |
| **`/v2/local`** | **2.0 本地多人模拟（裁判模式）** |
| **`/v2/rooms`** | **2.0 多人房间（创建/加入/公开列表）** |
| **`/v2/room/<id>`** | **2.0 多人房间对战（速度层结算）** |

### 运行测试

```bash
# 全部 1.0 测试
python -m pytest tests/test_logic.py tests/test_match.py tests/test_room.py tests/test_local.py tests/test_status.py tests/test_user_features.py -x -q

# 全部 2.0 测试
python -m pytest tests/test_game_v2.py tests/test_models_v2.py tests/test_room_v2.py -x -q

# 一键检查
.\scripts\check.ps1
```

---

## 🌐 在线部署

项目已适配 Railway + Cloudflare 生产部署。

**在线地址：** `https://clapclap.club`

```bash
git push origin main   # 推送自动触发 Railway 部署
```

### 生产环境变量

| 变量名 | 说明 |
|--------|------|
| `DATA_DIR` | 持久卷挂载路径（如 `/app/data`） |
| `EXPORT_TOKEN` | 数据库导出接口密码 |
| `BACKUP_GITHUB_TOKEN` | GitHub PAT（repo 权限），用于自动备份 |
| `BACKUP_GITHUB_REPO` | 备份目标仓库（如 `user/clapclap-backup.git`） |
| `BACKUP_INTERVAL_MINUTES` | 备份间隔（分钟），默认 30 |

---

## 🗺️ 开发路线图

### 2.0 多人化升级（10 阶段）

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Step 1** | 冻结 2.0 数字版结算规范 | ✅ 完成 |
| **Step 2** | 建立规则版本体系（1.0/2.0 并存） | ✅ 完成 |
| **Step 3** | 重构多人数据模型（PlayerStateV2/GameStateV2/RoomV2） | ✅ 完成 |
| **Step 4** | 独立实现 2.0 规则引擎（12 层速度结算） | ✅ 完成 |
| **Step 5** | 多人房间改造（参战/观战/房主/重赛） | ✅ 完成 |
| **Step 6** | 多人在线回合协议（目标选择/冲突协商/决策暂停恢复） | ✅ 完成 |
| **Step 7** | 前端页面改造（多人面板/决策 UI/速度层进度/聊天） | ✅ 完成 |
| **Step 8** | 匹配、本地模式与观战改造 | 🚧 准备开始 |
| **Step 9** | 记录、回放与战绩升级 | 🔜 待开发 |
| **Step 10** | 全量测试、迁移与分阶段上线 | 🔜 待开发 |

### 当前 2.0 实现快照

- [x] 规则规格：`develop/rule-spec-2.0.md`、判例表和流程图已形成数字版规则基础
- [x] 独立 v2 模型：`PlayerStateV2` / `GameStateV2` / `RoomV2` 与 1.0 并列
- [x] 独立 v2 引擎：支持速度层、三连、目标选择、冲突协商、暂停/恢复
- [x] v2 多人房间：创建、加入、准备、开始、退出、重赛投票、公开房间列表
- [x] v2 在线协议：出招、亮招、决策私发、结算进度、回合总结
- [x] v2 前端：多人玩家面板、动作区、决策弹窗、速度层条、结算日志、聊天、历史折叠设置
- [x] 隐私边界：未公开动作只给自己，决策选项只发给对应玩家，公开 payload 不暴露 player_token
- [x] 回归测试：当前核心测试覆盖 1.0 与 2.0，最近验证为 `177 passed`

### Step 8 工作清单

Step8 可以开始。当前基础已经满足“先邀请制多人房间，再公开房间，最后多人自动匹配”的前置条件；接下来重点不是再改规则引擎，而是把入口、观战和匹配体验补完整。

建议按这个顺序推进：

1. **冻结 Step8 范围**
   - [ ] 明确 Step8 不改 2.0 规则结算，只做匹配、本地模式、观战体验
   - [ ] 保留 1.0 匹配系统稳定运行，2.0 匹配使用独立 API/队列/前端入口
   - [ ] 确认 2.0 自动匹配第一版的目标人数策略：默认 4 人，可选 2~6 人

2. **观战增强**
   - [ ] v2 房间加入页支持“以观战者身份加入”
   - [ ] v2 房间页明确展示观战身份 banner
   - [ ] 观战者列表显示用户名，而不是只显示人数
   - [ ] 观战者可退出房间并清理本地身份
   - [ ] 对局中加入观战后，只能看公开动作和结算进度，不能提交动作或决策
   - [ ] 已死亡玩家的房间视图优化为观战态，保留死亡/名次信息

3. **2.0 本地模式收尾**
   - [ ] 对照在线 v2 的动作、速度层、总结展示，统一本地模式 UI 文案和样式
   - [ ] 本地模式增加可折叠详细日志，默认保持简洁
   - [ ] 检查本地模式是否复用最新 `GameEngineV2` 暂停/恢复语义
   - [ ] 补本地多人裁判模式的错误提示和操作说明

4. **公开房间体验完善**
   - [ ] 公开房间列表增加刷新状态、人数筛选和观战入口
   - [ ] 房间列表区分“可参战 / 可观战 / 已结束”
   - [ ] 有密码房间先隐藏或明确标记，避免加入流程半成品
   - [ ] 房间创建成功后保留清晰邀请方式：房间号 + 链接

5. **2.0 自动匹配骨架**
   - [ ] 新增独立 `app/v2/matchmaking.py`，不要复用 1.0 单等待槽
   - [ ] 新增 `/api/v2/match/*` 路由，按 `rule_version=2.0` 和目标人数分队列
   - [ ] 支持加入队列、取消排队、查询状态、匹配成功结果
   - [ ] 匹配成功后创建 v2 房间并返回各自 player_token
   - [ ] 第一版可以先不做复杂确认阶段，但要为确认阶段预留状态字段

6. **2.0 匹配前端**
   - [ ] `/v2` 大厅开放 2.0 匹配入口
   - [ ] 新增或改造 v2 匹配页面，显示当前目标人数、已匹配人数、取消按钮
   - [ ] 匹配成功后自动保存 `V2RoomIdentity` 并跳转 `/v2/room/<id>`
   - [ ] 网络断开或刷新后能恢复排队/匹配结果

7. **Step8 测试**
   - [ ] 观战加入/退出/权限测试
   - [ ] 死亡玩家观战态测试
   - [ ] v2 公开房间列表筛选/入口测试
   - [ ] v2 匹配队列基础测试：入队、取消、满员成房、不同人数不混队
   - [ ] v1/v2 匹配隔离测试，确保 1.0 自动匹配不受影响

### 1.0 已完成 ✅

- [x] 规则引擎核心（GameEngine）
- [x] SQLite 持久化（房间 + 匹配）
- [x] 本地双人模式（完整 UI）
- [x] 房间创建/加入/退出/恢复
- [x] 双方提交动作 → 统一结算
- [x] 双确认 reset
- [x] 匹配队列 → 自动配对 → 建房跳转
- [x] Socket.IO 实时同步 + 轮询兜底
- [x] Railway 部署 + Cloudflare 域名
- [x] 用户注册/登录系统（含访客登录）
- [x] Session 认证中间件（所有 API 受保护）
- [x] 账号管理（修改用户名/密码/介绍信/注销）
- [x] 管理员系统（查看/验证/注销用户）
- [x] 账号验证机制（30 天未验证自动注销）
- [x] 数据导出接口
- [x] GitHub 自动备份
- [x] 对战记录系统（JSON 存档，毫秒命名）
- [x] 用户主页与对局回放
- [x] 房间实时聊天
- [x] 用户注销后对局标记
- [x] Volume 持久卷挂载

### 后续计划 📋

- 2.0 Step 8（观战增强、本地模式收尾、公开房间体验、多人自动匹配）
- 2.0 Step 9-10（多人回放/战绩/迁移/上线）
- AI 模式接入（启发式 bot → 强化学习）
- 聚合战绩统计面板（胜率/常用动作/淘汰关系）
- 手机端适配完善
- 房间密码完整流程

详细路线图见 [`task.txt`](task.txt)。

---

## 📝 开发约定

### 架构原则

- **游戏状态以后端为准**，前端只负责展示和提交操作
- **规则引擎优先稳定**——1.0 `app/game.py` 不变，2.0 `app/v2/game.py` 独立演进
- **规则版本通过 `rule_version` 字段分发**，未知版本明确报错
- 核心规则正确性 > 界面效果 > 代码优雅
- 默认以最小修改、保持现有结构为原则

### 代码规范

- 所有 Python 导入使用绝对路径（`from app.xxx`、`from server.xxx`）
- API 路由统一使用 `/api/` 或 `/api/v2/` 前缀
- 前端共享逻辑通过 `core/` 模块（1.0/2.0 共用）
- 2.0 前端独立文件（`v2_*.js`），不与 1.0 混用
- 用户密码使用 SHA-256 + UID 盐值哈希
- Session token 通过 `X-Session-Token` 请求头传递
- 1.0 和 2.0 房间通过 `rule_version` 字段区分，同一个 SQLite 表

### 调试要点

- 前端问题：打开浏览器开发者工具查看 Console 和 Network
- 后端问题：查看 Flask 终端输出的 traceback
- 联机问题：检查 player_token、房间 ID、Socket.IO 连接状态
- 2.0 决策问题：检查 `settlement_progress_v2` 和 `decision_request_v2` Socket 事件
- 账号问题：检查 `data/users/` 下的用户文件夹和 CSV
- 对战记录：查看 `data/battles/` 下的 JSON 文件
- 缓存问题：刷新页面、清空 localStorage、使用无痕窗口测试

---

## 📄 许可

MIT License

---

> **ClapClap** —— 从一套原创手势规则，到双引擎多人网页游戏平台。
> 项目维护：[zhnzh2](https://github.com/zhnzh2)
