# ClapClap

ClapClap 是一个原创手势对战网页游戏项目。目前项目已经整理为 v1 和 v2 两套并列规则版本：

- v1: 1.0 双人对战版，包含本地模拟、双人房间、自动匹配、历史回放。
- v2: 2.0 多人对战版，支持最多 6 人、速度层结算、目标选择、冲突协商、观战、多人房间和自动匹配。

线上入口设计为：

- `https://clapclap.club/v1`
- `https://clapclap.club/v2`
- 访问 `https://clapclap.club/` 时自动跳转到 `/v1`

本地开发时对应：

- `http://127.0.0.1:5000/v1`
- `http://127.0.0.1:5000/v2`

## 当前状态

项目当前是一个 Flask + Socket.IO + 原生 JavaScript 的完整网页应用，包含账号系统、用户主页、对战存档、回放、房间聊天、管理员用户管理、数据校验和测试套件。

v1 和 v2 已经按版本拆分：

- 后端规则代码分别位于 `app/v1/` 和 `app/v2/`
- 页面模板分别位于 `server/templates/v1/` 和 `server/templates/v2/`
- 样式分别位于 `server/static/css/v1/` 和 `server/static/css/v2/`
- 页面脚本分别位于 `server/static/js/pages/v1/` 和 `server/static/js/pages/v2/`
- 联机脚本分别位于 `server/static/js/online/v1/` 和 `server/static/js/online/v2/`
- v1 API 使用 `/v1/api/...`
- v2 API 使用 `/v2/api/...`
- 登录页使用 `/v1/login` 和 `/v2/login`

少量共享能力保留在公共目录，例如用户系统、存储、对战记录、登录页、规则页、共享前端工具等。

## 功能概览

### v1: 1.0 双人版

v1 是双人规则版本，适合快速对战和规则练习。

主要功能：

- 本地双人模拟
- 在线双人房间
- 自动匹配
- 房间恢复
- 实时状态同步
- 回合历史和对局回放
- 房间聊天

主要入口：

| URL | 说明 |
| --- | --- |
| `/v1` | v1 大厅 |
| `/v1/local` | v1 本地模拟 |
| `/v1/rooms` | v1 房间列表 |
| `/v1/room/<room_id>` | v1 房间对战 |
| `/v1/match` | v1 自动匹配 |
| `/v1/rules` | v1 规则 |
| `/v1/user/<uid>` | v1 用户主页 |
| `/v1/record/<battle_id>` | v1 对局回放 |

### v2: 2.0 多人版

v2 是多人规则版本，核心是多玩家同步出招和速度层结算。

主要功能：

- 2 到 6 人多人对战
- 本地多人模拟
- 多人房间创建、加入、观战
- 自动匹配
- 速度层结算
- 目标选择
- 冲突协商
- 回合总结
- 多人战绩和回放

主要入口：

| URL | 说明 |
| --- | --- |
| `/v2` | v2 大厅 |
| `/v2/local` | v2 本地多人模拟 |
| `/v2/rooms` | v2 多人房间列表 |
| `/v2/room/<room_id>` | v2 多人房间对战 |
| `/v2/match` | v2 自动匹配 |
| `/v2/rules` | v2 规则 |
| `/v2/user/<uid>` | v2 用户主页 |
| `/v2/record/<battle_id>` | v2 对局回放 |

## 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 后端 | Python, Flask | 页面路由和 REST API |
| 实时通信 | Flask-SocketIO | 房间状态、聊天、v2 决策事件 |
| 前端 | 原生 JavaScript | 页面交互和动态渲染 |
| 模板 | Jinja2 | 服务端渲染 HTML |
| 存储 | SQLite + 文件系统 | 房间、匹配、用户、对战记录 |
| 测试 | pytest, node --check | 后端逻辑和前端语法检查 |
| 部署 | gunicorn / Railway / Cloudflare | 生产运行和域名访问 |

## 项目结构

```text
ClapClap/
├── app/
│   ├── v1/                      # v1 规则、模型、房间、匹配、本地状态
│   │   ├── constants.py
│   │   ├── game.py
│   │   ├── matchmaking.py
│   │   ├── models.py
│   │   ├── room_manager.py
│   │   └── state_api.py
│   ├── v2/                      # v2 多人规则、模型、房间、匹配、状态序列化
│   │   ├── constants.py
│   │   ├── game.py
│   │   ├── matchmaking.py
│   │   ├── models.py
│   │   ├── room.py
│   │   ├── room_manager.py
│   │   └── state_api.py
│   ├── battle_recorder.py       # 对战记录和回放数据
│   ├── storage.py               # SQLite 持久化工具
│   └── users.py                 # 用户、session、管理员、注销清理
│
├── server/
│   ├── app.py                   # Flask 应用入口
│   ├── auth_middleware.py       # 登录鉴权
│   ├── runtime.py               # 周期性清理
│   ├── socket_events.py         # v1 Socket.IO 事件
│   ├── socket_events_v2.py      # v2 Socket.IO 事件
│   ├── routes/                  # 页面和 API 路由
│   ├── services/                # 房间服务层
│   ├── templates/
│   │   ├── v1/                  # v1 页面模板
│   │   ├── v2/                  # v2 页面模板
│   │   ├── login.html           # 共享登录页
│   │   └── rule.html            # 共享规则页壳
│   └── static/
│       ├── css/
│       │   ├── v1/              # v1 样式
│       │   ├── v2/              # v2 样式
│       │   └── auth.css         # 共享登录/弹窗样式
│       └── js/
│           ├── core/            # API、session、storage、modal 等共享工具
│           ├── pages/
│           │   ├── v1/          # v1 页面脚本
│           │   └── v2/          # v2 页面脚本
│           └── online/
│               ├── v1/          # v1 联机脚本
│               └── v2/          # v2 联机脚本
│
├── tests/                       # pytest 测试
├── scripts/                     # 检查、迁移、数据校验脚本
├── data/                        # 本地数据目录
├── rules/                       # 规则文档
├── develop/                     # 设计和开发文档
├── requirements.txt
├── pytest.ini
└── README.md
```

## 快速开始

### 1. 安装依赖

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux 可使用：

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动服务

```powershell
python server/app.py
```

启动后访问：

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/v1`
- `http://127.0.0.1:5000/v2`

首次启动会初始化本地数据目录，并确保管理员账号存在。

### 3. 默认管理员账号

当前项目会确保存在管理员账号：

| 用户名 | 密码 |
| --- | --- |
| `zhnzh` | `207101` |

如用于正式部署，建议上线前修改默认密码或替换初始化逻辑。

## 测试和检查

运行全部测试：

```powershell
python -m pytest
```

运行完整检查脚本：

```powershell
.\scripts\check.ps1
```

`scripts/check.ps1` 会依次执行：

- pytest 全量测试
- `scripts/validate_data.py --strict --summary`
- Python 编译检查
- JavaScript 语法检查
- 模板内联 JavaScript 语法检查

也可以单独运行：

```powershell
python -m compileall app server scripts
node --check server/static/js/pages/v1/v1_home_page.js
python scripts/validate_data.py --strict --summary
```

## 数据目录

默认数据放在 `data/` 下。

典型内容：

```text
data/
├── clapclap.db                  # SQLite 数据库
├── users/                       # 用户和 session 数据
├── battles/                     # 对战记录 JSON
└── ...
```

主要数据类型：

- 用户数据由 `app/users.py` 管理
- 房间和匹配状态由 SQLite 持久化
- 对战记录由 `app/battle_recorder.py` 写入 JSON
- 用户注销会清理相关房间和匹配状态，并标记历史对局

生产环境建议通过 `DATA_DIR` 指向持久卷。

## 主要环境变量

| 变量 | 说明 |
| --- | --- |
| `DATA_DIR` | 数据目录。生产环境通常指向持久卷 |
| `EXPORT_TOKEN` | 数据库导出接口令牌 |
| `BACKUP_GITHUB_TOKEN` | 自动备份使用的 GitHub token |
| `BACKUP_GITHUB_REPO` | 自动备份目标仓库 |
| `BACKUP_INTERVAL_MINUTES` | 自动备份间隔，单位分钟 |

如果未配置备份相关变量，备份功能会自动禁用。

## API 约定

页面和业务 API 现在按版本分离：

```text
/v1/api/local/...
/v1/api/rooms/...
/v1/api/match/...

/v2/api/local/...
/v2/api/rooms/...
/v2/api/match/...
```

共享账号 API 也提供版本化入口：

```text
/v1/api/auth/...
/v1/api/user/...
/v1/api/admin/...
/v1/api/battles/...

/v2/api/auth/...
/v2/api/user/...
/v2/api/admin/...
/v2/api/battles/...
```

旧的 `/api/...` 仍保留为兼容别名，但前端应优先使用 `/v1/api/...` 或 `/v2/api/...`。

认证使用 `X-Session-Token` 请求头。前端由 `server/static/js/core/api.js` 自动携带。

## 前端缓存约定

前端使用 localStorage 保存登录态、房间身份、匹配状态和 UI 设置。

常见 key：

- `clapclap_session`
- `clapclap_server_boot_id`
- `clapclap_match_state`
- `clapclap_v2_match_state`
- `clapclap_room_<room_id>`
- `clapclap_v2_room_<room_id>`
- `clapclap_ui_settings_v2`
- `clapclap_v2_ui_settings`
- `clapclap_v2_room_ui_settings`

共享清理逻辑位于 `server/static/js/core/storage.js`。

## 开发约定

- 新增 v1 专属代码放入 `app/v1/`、`server/templates/v1/`、`server/static/.../v1/`
- 新增 v2 专属代码放入 `app/v2/`、`server/templates/v2/`、`server/static/.../v2/`
- 如果文件必须共享，放在公共目录，并避免写死 `/v1` 或 `/v2`
- 同一目录中同时存在版本文件时，使用 `v1_...` 和 `v2_...` 命名
- 页面跳转和 API 调用优先保持当前版本前缀
- 根路径 `/` 只负责跳转到 `/v1`
- 不要新增旧式 `/local`、`/rooms`、`/match` 等无版本页面入口
- v1 和 v2 规则引擎互不导入，公共能力才放在 `app/` 根目录

## 常用命令

```powershell
# 启动开发服务
python server/app.py

# 全量测试
python -m pytest

# 只跑 v2 规则测试
python -m pytest tests/test_game_v2.py tests/test_room_v2.py

# 数据校验
python scripts/validate_data.py --strict --summary

# 全量检查
.\scripts\check.ps1
```

## 部署说明

项目可部署到 Railway / gunicorn。

典型启动命令：

```bash
gunicorn server.app:app
```

如果需要 Socket.IO 的长连接能力，生产环境应确保部署平台支持 WebSocket。当前前端也保留 HTTP 轮询兜底。

线上域名建议配置：

```text
clapclap.club/    -> /v1
clapclap.club/v1  -> v1 大厅
clapclap.club/v2  -> v2 大厅
```

## 相关文档

- `rules/`: 规则书源文件
- `develop/`: 规则设计、流程图、发布计划等开发文档
- `task.txt`: 当前任务和阶段记录
- `tests/`: 行为测试和回归测试
- `scripts/validate_data.py`: 数据兼容性校验

## License

MIT License
