# ClapClap 👏

**拍拍** —— 双人手势对战网页游戏。类似石头剪刀布的策略博弈，但规则更复杂、资源更丰富、战术更深。

> 🎯 项目状态：**核心功能完整，账号系统、对战记录、实时聊天均已上线，产品化程度持续提升。**
>
> 已将 ClapClap 从一套原创规则，推进成为一个可部署、可联机、可匹配、带用户系统、对战存档和实时聊天的完整网页游戏。

---

## 🎮 游戏简介

ClapClap 是一个**回合制双人对战游戏**。每回合双方同时选择一个**动作（出招）**，由规则引擎统一结算。游戏有 18+ 种动作，分为四大类：

| 类别 | 动作 | 说明 |
|------|------|------|
| **资源** | 气、盾 | 获得基础资源 |
| **攻击（气系）** | gi、破、冷锋、如来、黑洞 | 气系攻击，各有攻防数值 |
| **攻击（盾系）** | Fire、闪电、烈焰、Shining | 盾系攻击，各有攻防数值 |
| **防御** | 十字防、八卦 | 高防御力抵挡攻击 |
| **锦囊** | 你吃、双吃、闪、镐 | 特殊策略：克制、闪避、抵挡伤害 |

### 核心规则亮点

- **非法动作直接判负** — 选择不可用的动作会直接输掉本回合
- **攻击与防御比较** — 攻击值 vs 防御值决定伤害和结果
- **等攻对掉** — 双方攻击值相等时互相抵消
- **闪** — 跳出本回合不受伤害
- **你吃 / 双吃** — 定向克制特定动作
- **资源优先级消耗** — 烈焰、Shining 等技能优先消耗特定资源
- **爆镐** — 镐在承受过量伤害或持有过多镐时会爆掉

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
| **创建时间** | 服务器时间记录账号创建时间 |
| **Session 认证** | 所有 API 自动携带 session token，未登录强制跳转 |

### 🎮 游戏模式

| 模式 | 说明 | 状态 |
|------|------|------|
| **🏠 本地双人模式** | 同屏操作，适合体验规则和本地测试 | ✅ 已完成 |
| **🏠 房间对战** | 创建/加入房间，与好友联机对战，身份恢复 | ✅ 已完成 |
| **🔍 自动匹配** | 进入匹配队列，自动配对在线玩家并跳转房间 | ✅ 已完成 |
| **💬 实时聊天** | 房间内参战/观战均可打字沟通，最多 50 字 | ✅ 已完成 |
| **🤖 AI 对战** | 入口已预留，计划接入启发式 bot 和强化学习模型 | 🔜 待开发 |

### 📊 数据与记录

| 功能 | 说明 |
|------|------|
| **对战记录** | 每局对战独立 JSON 存档，精确到毫秒命名 |
| **回合明细** | 每回合双方动作完整记录 |
| **Web 回放** | 分页展示历史战绩，可查看动作、伤害与资源快照 |
| **聊天存档** | 聊天记录与时间戳同步写入对局文件 |
| **用户索引** | 每个用户文件夹下记录参与过的所有对局 |
| **注销标记** | 用户注销后标记关联对局，全员注销移入 rub/ |
| **数据导出** | API 一键下载 SQLite 数据库 |
| **自动备份** | 定时推送到 GitHub 私有仓库 |

### 🔧 技术特性

- **⚡ 实时同步** — 基于 Socket.IO 的房间状态实时推送，WebSocket + 轮询双通道兜底
- **💾 持久化存储** — SQLite 存储房间和匹配状态，用户文件系统存储账号数据
- **📁 对战存档** — JSON 文件存储每局完整记录（参与者、回合、聊天、胜负）
- **🎨 响应式 UI** — 支持桌面和移动端，紧凑模式适配 150% 缩放，键盘快捷键
- **📜 对局历史** — 每回合详细结算记录可查
- **🔐 身份系统** — session token + player_token 双重认证
- **🗑️ 账号注销** — 不可逆删除，自动清理关联房间/匹配/对局标记

---

## 🛠 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| **后端框架** | Python / Flask | Web 应用与 RESTful API |
| **实时通信** | Flask-SocketIO | 房间状态 + 聊天实时推送 |
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
│                    前端层 (Jinja2 + 原生 JS)                 │
│  模板页面 → Socket.IO 客户端 → localStorage 缓存           │
│  core/: ApiUtils / MessageUtils / ModalUtils / BootUtils   │
│        / SessionUtils                                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                  服务层 (Flask + SocketIO)                   │
│  HTTP Routes (pages/local/room/match/auth/admin)           │
│  Socket Events (join/submit/reset/chat)                    │
│  Auth Middleware (require_auth decorator)                  │
│  Services (room_service.py)                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 核心引擎层 (app/)                            │
│  GameEngine → 回合结算                                      │
│  RoomManager → 房间生命周期                                  │
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
├── app/                         # 核心引擎层
│   ├── __init__.py
│   ├── constants.py             # 动作枚举、数值常量
│   ├── game.py                  # 规则引擎（回合结算核心）
│   ├── models.py                # 数据模型（GameState / PlayerState）
│   ├── matchmaking.py           # 匹配队列管理
│   ├── room_manager.py          # 房间管理（生命周期 + 聊天）
│   ├── state_api.py             # 状态序列化（网络/持久化）
│   ├── storage.py               # SQLite 持久化
│   ├── users.py                 # 用户存储与鉴权（CSV + 文件系统）
│   └── battle_recorder.py       # 对战记录（JSON 存档）
│
├── server/                      # Flask 服务层
│   ├── __init__.py
│   ├── app.py                   # 应用入口与工厂
│   ├── extensions.py            # Flask 扩展初始化
│   ├── socket_events.py         # WebSocket 事件处理（含聊天）
│   ├── runtime.py               # 运行环境 + 周期性清理
│   ├── backup.py                # GitHub 自动备份
│   ├── auth_middleware.py        # require_auth 装饰器
│   ├── routes/                  # HTTP 路由
│   │   ├── page_routes.py       #   页面路由（含 /login）
│   │   ├── local_routes.py      #   本地模式 API
│   │   ├── room_routes.py       #   房间 API（session 认证）
│   │   ├── match_routes.py      #   匹配 API（session 认证）
│   │   ├── status_routes.py     #   状态检查 API
│   │   ├── export_routes.py     #   数据库导出 API
│   │   └── auth_routes.py       #   认证 + 管理员 API
│   ├── services/                # 业务逻辑层
│   │   └── room_service.py      #   房间服务（含对战记录集成）
│   ├── templates/               # Jinja2 模板
│   │   ├── login.html           #   登录/注册页
│   │   ├── home.html            #   主页（模式大厅）
│   │   ├── local.html           #   本地双人模式
│   │   ├── rooms.html           #   房间列表
│   │   ├── room_detail.html     #   房间对战详情（含聊天）
│   │   ├── match.html           #   匹配模式
│   │   ├── ai.html              #   AI 模式（预留）
│   │   ├── user.html            #   用户主页与历史战绩
│   │   └── record.html          #   对局回放
│   └── static/                  # 前端资源
│       ├── css/
│       │   ├── auth.css         #   登录/账号/弹窗样式
│       │   ├── local.css        #   本地模式样式
│       │   ├── rooms.css        #   房间列表样式
│       │   ├── match.css        #   匹配模式样式
│       │   └── room_detail*.css #   房间详情样式（含聊天）
│       └── js/
│           ├── socket.io.min.js #   Socket.IO 客户端
│           ├── core/            #   共享模块
│           │   ├── api.js       #     API 请求封装（自动携带 session）
│           │   ├── boot.js      #     启动检测与状态恢复
│           │   ├── message.js   #     消息提示
│           │   ├── modal.js     #     弹窗系统
│           │   ├── session.js   #     前端 session 管理
│           │   └── storage.js   #     localStorage 工具
│           ├── online/          #   联机逻辑
│           │   ├── room_state.js
│           │   ├── room_identity.js
│           │   ├── resume_room.js
│           │   ├── match_state.js
│           │   ├── history_renderer.js
│           │   ├── round_result_renderer.js
│           │   └── player_state_renderer.js
│           └── pages/           #   页面入口
│               ├── login_page.js
│               ├── home_page.js
│               ├── local_page.js / local_page_data.js / local_page_ui.js
│               ├── rooms_page.js
│               ├── room_detail_page.js / room_detail_data.js
│               ├── match_page.js
│               ├── user_page.js / record_page.js
│               ├── account_modal.js       #   账号管理弹窗
│               └── admin_users_modal.js   #   管理员用户管理弹窗
│
├── data/                         # 数据目录（生产环境挂载 Volume）
│   ├── clapclap.db               # SQLite 数据库
│   ├── users/                    # 用户数据
│   │   ├── users.csv             #   用户索引（UID,用户名,密码,创建时间,已验证,权限）
│   │   └── User_X/               #   各用户文件夹（username/password/intro/session/...）
│   └── battles/                  # 对战记录
│       ├── 202606161954013847.json
│       └── rub/                  #   全员注销的对局（待清理）
│
├── tests/                       # 单元测试
│   ├── test_logic.py            # 规则引擎核心测试
│   ├── test_match.py            # 匹配逻辑测试
│   ├── test_room.py             # 房间管理测试
│   ├── test_status.py           # 状态检查测试
│   └── test_user_features.py    # 用户密码、战绩并发与分页测试
│
├── scripts/
│   └── check.ps1                # 一键检查脚本
│
├── rules/                       # LaTeX 规则文档
│   ├── version 1.0/
│   └── version 2.0/
│
├── requirements.txt             # Python 依赖
├── README.md                    # 本文件
├── task.txt                     # 开发路线图
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

打开浏览器访问 `http://127.0.0.1:5000`。

首次启动会自动创建 admin 账号：用户名 `zhnzh`，密码 `207101`。

### 运行测试

```bash
python -m unittest discover -s tests -v
```

### 一键检查

```powershell
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

### 部署注意事项

- **持久化**：生产环境必须挂载 Railway Volume，路径通过 `DATA_DIR` 指定
- **备份**：配置 GitHub token 和仓库后，数据库定时自动备份
- **域名**：已接入 Cloudflare DNS + SSL
- **API Key**：不硬编码在代码中，通过环境变量管理

---

## 🗺️ 开发路线图

### 已完成 ✅

- [x] 规则书 1.0 / 2.0 版本体系
- [x] 规则引擎核心（GameEngine）
- [x] SQLite 持久化（房间 + 匹配）
- [x] 本地双人模式（完整 UI）
- [x] 房间创建/加入/退出/恢复
- [x] 双方提交动作 → 统一结算
- [x] 双确认 reset
- [x] 匹配队列 → 自动配对 → 建房跳转
- [x] Socket.IO 实时同步 + 轮询兜底
- [x] Railway 部署 + Cloudflare 域名
- [x] 自动化测试（63 个用例）
- [x] **用户注册/登录系统**（含访客登录）
- [x] **Session 认证中间件**（所有 API 受保护）
- [x] **账号管理**（修改用户名/密码/介绍信/注销）
- [x] **管理员系统**（查看/验证/注销用户）
- [x] **账号验证机制**（30 天未验证自动注销）
- [x] **数据导出接口**（带 token 鉴权）
- [x] **GitHub 自动备份**（定时推送数据库）
- [x] **对战记录系统**（JSON 存档，毫秒命名）
- [x] **用户主页与对局回放**（分页战绩、完整回合明细）
- [x] **房间实时聊天**（50 字限制，存档到对局）
- [x] **用户注销后对局标记**（rub 回收站）
- [x] Volume 持久卷挂载

### 进行中 🔄

- UI 风格统一与打磨
- 联机体验优化（异常处理、提示统一）

### 计划中 📋

- AI 模式接入（启发式 bot → 强化学习）
- 观战模式增强
- 邀请体验优化
- 房主机制
- 聚合胜率、常用动作等统计面板
- 小屏/手机端适配完善

详细路线图见 [`task.txt`](task.txt)。

---

## 📝 开发约定

### 架构原则

- **游戏状态以后端为准**，前端只负责展示和提交操作
- **规则引擎（`app/game.py`）** 优先保持稳定，AI 和前端不直接绕过规则引擎
- 核心规则正确性 > 界面效果 > 代码优雅
- 默认以最小修改、保持现有结构为原则

### 代码规范

- 所有 Python 导入使用绝对路径（`from app.xxx`、`from server.xxx`）
- API 路由统一使用 `/api/` 前缀
- 前端共享逻辑通过 `core/` 模块
- 用户密码使用 SHA-256 + UID 盐值哈希
- Session token 通过 `X-Session-Token` 请求头传递

### 调试要点

- 前端问题：打开浏览器开发者工具查看 Console 和 Network
- 后端问题：查看 Flask 终端输出的 traceback
- 联机问题：检查 player_token、房间 ID、Socket.IO 连接状态
- 账号问题：检查 `data/users/` 下的用户文件夹和 CSV
- 对战记录：查看 `data/battles/` 下的 JSON 文件
- 缓存问题：刷新页面、清空 localStorage、使用无痕窗口测试

---

## 📄 许可

MIT License

---

> **ClapClap** — 从一套原创规则，到可部署、可联机、可匹配的完整网页游戏。
> 项目维护：[zhnzh2](https://github.com/zhnzh2)
