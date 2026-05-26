# ClapClap 👏

双人手势对战网页游戏 —— 类似石头剪刀布的策略博弈，但规则更复杂、资源更丰富、战术更深。

## 🎮 游戏简介

ClapClap 是一个回合制双人对战游戏。每回合双方同时选择一个**动作**（出招），由规则引擎统一结算。游戏有 18+ 种动作，分为四大类：

| 类别 | 动作 | 说明 |
|------|------|------|
| **资源** | 气、盾 | 获得基础资源 |
| **攻击** | gi、破、冷锋、如来、黑洞 / Fire、闪电、烈焰、Shining | 气系/盾系攻击，各有攻防数值 |
| **防御** | 十字、八卦 | 高防御力抵挡攻击 |
| **锦囊** | 你吃、双吃、闪、镐 | 特殊策略：克制、闪避、抵挡伤害 |

详细规则见 [`rules/`](rules/) 目录中的 LaTeX 文档。

## ✨ 功能特性

- **🏠 本地双人模式** — 同屏操作，适合体验规则和测试
- **🏠 房间对战** — 创建/加入房间，与好友联机对战，支持邀请链接
- **🔍 自动匹配** — 进入匹配队列，自动配对在线玩家
- **⚡ 实时同步** — 基于 Socket.IO 的房间状态实时推送
- **💾 持久化存储** — SQLite 存储房间和匹配状态，重启不丢失
- **🎨 响应式 UI** — 支持桌面和移动端，紧凑模式适配 150% 缩放
- **⌨️ 键盘快捷键** — 完整的键盘操作支持
- **📜 对局历史** — 每回合详细结算记录可查
- **🤖 AI 对战** — 入口已预留，后续接入

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python / Flask / Flask-SocketIO |
| 前端 | 原生 JavaScript（无框架） |
| 存储 | SQLite |
| 实时通信 | Socket.IO |
| 部署 | gunicorn / Railway |

## 📁 项目结构

```
ClapClap/
├── app/                     # 核心引擎
│   ├── constants.py         #   动作枚举、数值常量
│   ├── game.py              #   规则引擎（回合结算）
│   ├── models.py            #   数据模型（GameState / PlayerState）
│   ├── matchmaking.py       #   匹配队列
│   ├── room_manager.py      #   房间管理
│   ├── state_api.py         #   状态序列化
│   └── storage.py           #   SQLite 持久化
├── server/                  # Flask 服务
│   ├── app.py               #   应用入口
│   ├── socket_events.py     #   WebSocket 事件
│   ├── services/            #   业务逻辑层
│   ├── routes/              #   HTTP 路由
│   ├── templates/           #   Jinja2 模板
│   └── static/              #   前端资源
│       ├── css/             #     样式表
│       └── js/
│           ├── lib/         #       第三方库
│           ├── core/        #       共享工具
│           ├── online/      #       联机逻辑
│           └── pages/       #       页面逻辑
├── tests/                   # 单元测试（51 个用例）
├── scripts/                 # 开发工具
└── rules/                   # LaTeX 规则文档
```

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

# 启动服务
python server/app.py
```

打开浏览器访问 `http://127.0.0.1:5000`。

### 运行测试

```bash
python -m unittest discover -s tests -v
```

### 一键检查

```powershell
.\scripts\check.ps1
```

## 🌐 部署

项目已适配 Railway 部署。推送 `main` 分支即可自动触发部署。

```bash
# 确保环境变量已设置（Railway 上通过 Dashboard 配置）
# OPENROUTER_API_KEY  （后续 AI 模式需要）
```

## 📝 开发约定

- 游戏状态**以后端为准**，前端只负责展示和提交
- 规则引擎 **`app/game.py`** 优先保持稳定
- 文件原则上不超过 600 行（CSS 和单体 JS 除外）
- 所有 Python 导入使用绝对路径（`from app.xxx`、`from server.xxx`）
- API 路由统一使用 `/api/` 前缀

## 📄 许可

MIT License
