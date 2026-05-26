# ClapClap 👏

**拍拍** —— 双人手势对战网页游戏。类似石头剪刀布的策略博弈，但规则更复杂、资源更丰富、战术更深。

> 🎯 项目状态：**核心功能完整，联机链路可用，正在从原型走向更稳更顺的产品化版本。**
>
> 已将 ClapClap 从一套原创规则，推进成为一个可部署、可联机、可匹配、带持久化和实时同步的网页游戏原型。

---

## 🎮 游戏简介

ClapClap 是一个**回合制双人对战游戏**。每回合双方同时选择一个**动作（出招）**，由规则引擎统一结算。游戏有 18+ 种动作，分为四大类：

| 类别 | 动作 | 说明 |
|------|------|------|
| **资源** | 气、盾 | 获得基础资源 |
| **攻击（气系）** | gi、破、冷锋、如来、黑洞 | 气系攻击，各有攻防数值 |
| **攻击（盾系）** | Fire、闪电、烈焰、Shining | 盾系攻击，各有攻防数值 |
| **防御** | 十字、八卦 | 高防御力抵挡攻击 |
| **锦囊** | 你吃、双吃、闪、镐 | 特殊策略：克制、闪避、抵挡伤害 |

### 核心规则亮点

- **非法动作直接判负** — 选择不可用的动作会直接输掉本回合
- **攻击与防御比较** — 攻击值 vs 防御值决定伤害和结果
- **等攻对掉** — 双方攻击值相等时互相抵消
- **闪** — 跳出本回合不受伤害
- **你吃 / 双吃** — 定向克制特定动作
- **资源优先级消耗** — 烈焰、Shining 等技能优先消耗特定资源
- **爆镐** — 镐在承受过量伤害时会爆掉

详细规则见 [`rules/`](rules/) 目录中的 LaTeX 文档。

---

## ✨ 功能特性

### 🎮 游戏模式

| 模式 | 说明 | 状态 |
|------|------|------|
| **🏠 本地双人模式** | 同屏操作，适合体验规则和本地测试 | ✅ 已完成 |
| **🏠 房间对战** | 创建/加入房间，与好友联机对战，支持身份恢复 | ✅ 已完成 |
| **🔍 自动匹配** | 进入匹配队列，自动配对在线玩家并跳转房间 | ✅ 已完成 |
| **🤖 AI 对战** | 入口已预留，计划接入启发式 bot 和强化学习模型 | 🔜 待开发 |

### 🔧 技术特性

- **⚡ 实时同步** — 基于 Socket.IO 的房间状态实时推送，WebSocket + 轮询双通道兜底
- **💾 持久化存储** — SQLite 存储房间和匹配状态，服务重启不丢失，支持状态恢复
- **🎨 响应式 UI** — 支持桌面和移动端，紧凑模式适配 150% 缩放，支持键盘快捷键
- **📜 对局历史** — 每回合详细结算记录可查，包含双方动作、资源变化、结算说明
- **🔐 身份系统** — player_token 机制确保玩家身份安全，页面刷新后可恢复房间状态
- **🔄 双确认 reset** — 双方确认后才重置游戏，防止误操作

---

## 🛠 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| **后端框架** | Python / Flask | Web 应用与 RESTful API |
| **实时通信** | Flask-SocketIO | 房间状态实时推送 |
| **前端** | 原生 JavaScript（无框架） | 页面交互与动态渲染 |
| **模板** | Jinja2 | 服务端页面渲染 |
| **存储** | SQLite | 房间与匹配状态持久化 |
| **部署** | gunicorn / Railway + Cloudflare | 生产运行与域名访问 |

### 项目架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端层 (Jinja2 + 原生 JS)                 │
│  模板页面 → Socket.IO 客户端 → localStorage 缓存           │
│  core/: ApiUtils / MessageUtils / ModalUtils / BootUtils   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                  服务层 (Flask + SocketIO)                   │
│  HTTP Routes (pages/local/room/match)                      │
│  Socket Events (join/leave/submit/reset)                   │
│  Services (server/services/room_service.py)                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 核心引擎层 (app/)                            │
│  GameEngine → 回合结算                                      │
│  RoomManager → 房间生命周期                                  │
│  Matchmaking → 匹配队列                                     │
│  Storage → SQLite 持久化                                    │
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
│   ├── room_manager.py          # 房间管理（生命周期）
│   ├── state_api.py             # 状态序列化（网络/持久化）
│   └── storage.py               # SQLite 持久化
│
├── server/                      # Flask 服务层
│   ├── __init__.py
│   ├── app.py                   # 应用入口与工厂
│   ├── extensions.py            # Flask 扩展初始化
│   ├── socket_events.py         # WebSocket 事件处理
│   ├── runtime.py               # 运行环境检测
│   ├── room_service.py          # 房间业务逻辑（历史兼容入口）
│   ├── routes/                  # HTTP 路由
│   │   ├── page_routes.py       #   页面路由（主页/本地/房间/匹配）
│   │   ├── local_routes.py      #   本地模式 API
│   │   ├── room_routes.py       #   房间 API
│   │   ├── match_routes.py      #   匹配 API
│   │   └── status_routes.py     #   状态检查 API
│   ├── services/                # 业务逻辑层
│   │   └── room_service.py      #   房间服务（当前路由使用）
│   ├── templates/               # Jinja2 模板
│   │   ├── home.html            #   主页
│   │   ├── local.html           #   本地双人模式
│   │   ├── rooms.html           #   房间列表
│   │   ├── room_detail.html     #   房间对战详情
│   │   ├── match.html           #   匹配模式
│   │   └── ai.html              #   AI 模式（预留）
│   └── static/                  # 前端资源
│       ├── css/
│       │   ├── local.css        #   本地模式样式
│       │   ├── rooms.css        #   房间列表样式
│       │   ├── match.css        #   匹配模式样式
│       │   └── room_detail*.css #   房间详情样式
│       └── js/
│           ├── socket.io.min.js #   Socket.IO 客户端
│           ├── lib/             #   工具库
│           ├── core/            #   共享模块
│           │   ├── api.js       #     API 请求封装
│           │   ├── boot.js      #     启动检测与状态恢复
│           │   ├── message.js   #     消息提示
│           │   ├── modal.js     #     弹窗系统
│           │   └── storage.js   #     localStorage 工具
│           ├── online/          #   联机逻辑
│           │   ├── room_state.js
│           │   ├── room_identity.js
│           │   ├── resume_room.js
│           │   ├── history_renderer.js
│           │   ├── round_result_renderer.js
│           │   └── player_state_renderer.js
│           └── pages/           #   页面入口
│               ├── home_page.js
│               ├── local_page.js / local_page_data.js / local_page_ui.js
│               ├── rooms_page.js
│               ├── room_detail_page.js / room_detail_data.js
│               └── match_page.js
│
├── tests/                       # 单元测试
│   ├── test_logic.py            # 规则引擎核心测试
│   ├── test_match.py            # 匹配逻辑测试
│   ├── test_room.py             # 房间管理测试
│   └── test_status.py           # 状态检查测试
│
├── scripts/
│   └── check.ps1                # 一键检查脚本
│
├── rules/                       # LaTeX 规则文档
│   ├── version 1.0/
│   └── version 2.0/
│
├── task.txt                     # 开发路线图与任务追踪
├── requirements.txt             # Python 依赖
└── README.md                    # 本文件
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+

### 安装运行

```bash
# 克隆仓库
git clone https://github.com/your-username/ClapClap.git
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

### 运行测试

```bash
# 运行全部测试
python -m unittest discover -s tests -v

# 运行特定测试
python -m unittest tests.test_logic -v
python -m unittest tests.test_room -v
python -m unittest tests.test_match -v
```

### 一键检查

```powershell
.\scripts\check.ps1
```

---

## 🌐 在线部署

项目已适配 Railway + Cloudflare 生产部署。

```bash
# 推送 main 分支自动触发 Railway 部署
git push origin main

# 生产环境启动（由 Railway Procfile 控制）
# gunicorn --worker-class eventlet -w 1 server.app:app
```

### 部署注意事项

- **持久化**：生产环境需挂载 Railway Volume，`.db` 文件不进仓库
- **环境变量**：`OPENROUTER_API_KEY`（后续 AI 模式需要）通过 Railway Dashboard 配置
- **域名**：已接入 Cloudflare DNS + SSL

---

## 🗺️ 开发路线图

### 已完成 ✅

- [x] 规则书 1.0 / 2.0 版本体系
- [x] 规则引擎核心（GameEngine）
- [x] 数据模型与状态序列化
- [x] SQLite 持久化（房间 + 匹配）
- [x] 本地双人模式（完整 UI）
- [x] 房间创建/加入/退出/恢复
- [x] 双方提交动作 → 统一结算
- [x] 双确认 reset
- [x] 匹配队列 → 自动配对 → 建房跳转
- [x] 匹配状态恢复与取消匹配
- [x] player_token 身份系统
- [x] Socket.IO 实时同步 + 轮询兜底
- [x] 房间 / 匹配 / API / Socket.IO 自动化测试
- [x] Railway 部署 + Cloudflare 域名
- [x] 主页/房间列表/匹配页面

### 进行中 🔄

- 联机体验打磨（提示统一、异常处理、过渡动画）
- 前端结构与状态流整理（模块拆分、统一入口）
- 联机外围测试补强
- UI 风格统一（弹窗、状态区、历史记录）

### 计划中 📋

- AI 模式接入（启发式 bot → 强化学习）
- 战绩与对局统计
- 观战模式
- 邀请体验优化
- 房主机制
- 小屏/手机端适配完善

详细开发路线图见 [`task.txt`](task.txt)。

---

## 📝 开发约定

### 架构原则

- **游戏状态以后端为准**，前端只负责展示和提交操作
- **规则引擎（`app/game.py`）** 优先保持稳定，AI 和前端不直接绕过规则引擎
- 核心规则正确性 > 界面效果 > 代码优雅
- 默认以最小修改、保持现有结构为原则，不轻易推倒重来

### 代码规范

- 文件原则上不超过 600 行（CSS 和单体 JS 除外）
- 所有 Python 导入使用绝对路径（`from app.xxx`、`from server.xxx`）
- API 路由统一使用 `/api/` 前缀
- 前端共享逻辑统一通过 `core/` 模块（ApiUtils / MessageUtils / ModalUtils / BootUtils）

### 调试要点

- 前端问题：打开浏览器开发者工具查看 Console 和 Network
- 后端问题：查看 Flask 终端输出的 traceback
- 联机问题：注意检查 player_token、房间 ID、Socket.IO 连接状态
- 缓存问题：刷新页面、清空 localStorage、使用无痕窗口测试

---

## 📄 许可

MIT License

---

> **ClapClap** — 从一套原创规则，到可部署、可联机、可匹配的网页游戏原型。  
> 项目维护：[zhnzh2](https://github.com/zhnzh2)
