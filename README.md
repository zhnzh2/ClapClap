# ClapClap

ClapClap 是一个原创手势对战网页游戏，当前线上版本按规则分为两条线：

- `v1`: 1.0 双人版，包含本地模拟、AI 对战、双人房间、自动匹配和回放。
- `v2`: 2.0 多人版，支持 2 到 6 人、速度层结算、目标选择、多人房间、观战和回放。

线上入口：

- `https://clapclap.club/`
- `https://clapclap.club/v1`
- `https://clapclap.club/v2`

本地入口：

- `http://127.0.0.1:5000/v1`
- `http://127.0.0.1:5000/v2`

## 当前功能

### 1.0 双人版

- 本地双人模拟
- 网页端 AI 对战
- AI 难度选择：简单、普通、困难
- 困难模式模型部署检查和启发式降级
- 在线双人房间
- 自动匹配
- 房间刷新恢复
- 房间聊天
- 对局记录和回放
- 用户主页、战绩筛选、对局导出

常用入口：

| URL | 说明 |
| --- | --- |
| `/v1` | 1.0 大厅 |
| `/v1/ai` | 1.0 AI 对战 |
| `/v1/local` | 1.0 本地双人模拟 |
| `/v1/rooms` | 1.0 房间列表 |
| `/v1/match` | 1.0 自动匹配 |
| `/v1/rules` | 1.0 规则 |
| `/v1/user/<uid>` | 用户主页 |
| `/v1/record/<battle_id>` | 对局回放 |

### 2.0 多人版

- 本地多人模拟
- 2 到 6 人多人房间
- 自动匹配
- 观战
- 多玩家同步决策
- 速度层结算
- 目标选择
- 冲突协商
- 多人战绩和回放

常用入口：

| URL | 说明 |
| --- | --- |
| `/v2` | 2.0 大厅 |
| `/v2/local` | 2.0 本地多人模拟 |
| `/v2/rooms` | 2.0 房间列表 |
| `/v2/match` | 2.0 自动匹配 |
| `/v2/rules` | 2.0 规则 |
| `/v2/user/<uid>` | 用户主页 |
| `/v2/record/<battle_id>` | 对局回放 |

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python, Flask |
| 实时通信 | Flask-SocketIO |
| 前端 | 原生 JavaScript, Jinja2 |
| 存储 | SQLite, CSV, JSON 文件 |
| 测试 | pytest, node --check |
| 部署 | gunicorn, Railway |
| AI 训练 | Gymnasium, Stable-Baselines3, sb3-contrib |

生产依赖在 `requirements.txt`，训练依赖单独放在 `requirements-train.txt`。线上服务默认不安装训练依赖，也不在 Web 请求里训练模型。

## 仓库结构

```text
ClapClap/
├── app/
│   ├── ai/                      # 1.0 AI 策略、动作空间、模型运行时检查
│   ├── v1/                      # 1.0 规则、状态、房间、匹配
│   ├── v2/                      # 2.0 规则、状态、房间、匹配
│   ├── ai_env.py                # 训练环境元数据校验
│   ├── battle_recorder.py       # 对战记录、回放、训练样本导出
│   ├── storage.py               # SQLite 数据目录和连接工具
│   └── users.py                 # 用户、session、管理员、注销清理
│
├── server/
│   ├── app.py                   # Flask / Socket.IO 应用入口
│   ├── auth_middleware.py       # 登录鉴权
│   ├── backup.py                # 数据备份
│   ├── runtime.py               # 全局运行状态和周期清理
│   ├── socket_events.py         # 1.0 Socket.IO 事件
│   ├── socket_events_v2.py      # 2.0 Socket.IO 事件
│   ├── routes/                  # 页面路由和 API
│   ├── services/                # 房间服务层
│   ├── templates/               # Jinja2 页面模板
│   └── static/                  # CSS、前端 JS、Socket.IO 客户端
│
├── training/                    # 离线训练脚本和训练样本工具
├── tests/                       # pytest 测试
├── scripts/                     # 检查、评估、迁移、数据校验脚本
├── rules/                       # 规则文档源文件和发布版 PDF
├── Procfile                     # Railway / gunicorn 启动配置
├── requirements.txt             # 生产依赖
├── requirements-train.txt       # 离线训练依赖
├── runtime.txt                  # Python 运行时版本
└── README.md
```

本地数据、开发报告、训练输出、模型开发缓存、LaTeX 中间文件和个人工具配置不会进入仓库。

## 快速开始

### 安装生产依赖

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux：

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 启动本地服务

```powershell
python server/app.py
```

打开：

```text
http://127.0.0.1:5000/
```

首次启动会初始化 `data/`，并确保管理员账号 `zhnzh`（UID=0）存在。
管理员初始密码从后端环境变量 `CLAPCLAP_ADMIN_PASSWORD` 读取；未设置时会生成一次性随机密码并只在服务器启动日志中输出。项目不存在可直接登录生产环境的固定默认密码。

## AI 对战和训练

1.0 AI 对战入口是：

```text
/v1/ai
```

当前 AI 策略：

- 简单：随机合法动作
- 普通：启发式策略
- 困难：进入对战前检查所选模型；模型不可用时自动降级为保守启发式

当前模型槽位：

- `ClapFish2`：当前生产 deploy 模型，也是默认选择。
- `ClapFish1`：历史模型，已归档但仍可在网页模型槽位 1 中用于对战和对比。

ClapFish2 在 3 个 seed、每个 matchup 200 局的晋级评估中，对 normal、hard 和 ClapFish1 均为 100% 胜率；对 easy 为 96.0%～98.5%，对 random 为 94.5%～96.5%。三轮评估均为 0 非法动作、0 fallback、0 超时，P95 推理时间低于 2ms。评估结果只代表当前规则和对手集合，不等同于对所有真人策略都能保持相同胜率。

AI 不重新实现规则。训练环境和推理都必须通过 `app/v1/game.py` 的规则引擎，不能复制一份规则逻辑。

离线训练依赖：

```powershell
pip install -r requirements-train.txt
```

训练和评估相关入口：

```powershell
python scripts/evaluate_ai.py --model-dir models/ai/v1/dev --matrix --games 200 --seed 20260630 --output reports/ai_eval/candidate.json
python scripts/evaluate_ai.py --model-dir models/ai/v1/dev --opponent-model-dir models/ai/v1/deploy --matrix --games 200 --seed 20260701 --output reports/ai_eval/candidate_seed2.json
python scripts/promote_ai_model.py --model-dir models/ai/v1/dev --eval-report reports/ai_eval/candidate.json reports/ai_eval/candidate_seed2.json --dry-run
python -m training.human_ai_samples exports/a.zip exports/b.zip -o training/data/human_ai_samples.jsonl
```

晋级会逐个检查每份 seed 报告，要求报告完整包含 easy、normal、hard、random，并检查 hard 最低胜率、P1/P2 差异、非法动作、截断、双败、动作集中度、fallback、超时率和 P95 推理耗时。正式执行 promote 前应始终先运行 `--dry-run`。

## 欢迎贡献 AI 训练数据

ClapClap 的 AI 需要真实玩家数据。最有价值的数据不是“AI 自己打自己”，而是人类在不同资源、不同血量、不同局势下如何应对 AI。

你可以这样贡献：

1. 在 `/v1/ai` 多打几局 AI 对战。
2. 打开用户主页。
3. 在对局记录里筛选 `AI 人机对战`。
4. 点击打包下载。
5. 导出的 ZIP 中会包含 `training/ai_battle_samples.jsonl`。
6. 可以把 ZIP 或 JSONL 交给维护者，或在 PR 中说明数据来源和大致局数。

本地合并多个导出文件：

```powershell
python -m training.human_ai_samples exports\a.zip exports\b.zip -o training\data\human_ai_samples.jsonl
```

贡献数据时请注意：

- 不要提交真实密码、token、私钥或个人敏感信息。
- 尽量保留完整对局，不要只挑赢局。
- 简单、普通、困难都可以贡献。
- 如果你发现 AI 某类局势特别弱，欢迎附上复现说明。

这些数据后续可以用于：

- 行为克隆
- 回归评估
- 起手库和局势分析
- PPO/self-play 训练前后的质量对比

## 测试

运行 AI 相关测试：

```powershell
python -m pytest -q tests/test_ai_routes.py tests/test_ai_rules.py tests/test_ai_env.py
```

运行全部测试：

```powershell
python -m pytest
```

pytest 会为每个测试创建独立 `DATA_DIR`，并在测试前后清理 AI session、v1/v2 房间、匹配队列、登录限流和 v2 Socket 身份，避免全局状态与真实 `data/` 相互污染。

运行完整检查：

```powershell
.\scripts\check.ps1
```

`scripts/check.ps1` 会执行 pytest、数据校验、Python 编译检查、前端 JS 语法检查和模板内联 JS 检查。

## 数据目录

默认数据目录是 `data/`。生产环境建议通过 `DATA_DIR` 指向持久卷。

典型内容：

```text
data/
├── clapclap.db
├── users/
└── battles/
```

主要数据：

- SQLite：房间、匹配等状态
- CSV + 用户目录：用户和 session
- JSON：对战记录、回放、训练样本导出

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `DATA_DIR` | 数据目录，生产环境通常指向 Railway Volume |
| `EXPORT_TOKEN` | 数据导出接口令牌 |
| `BACKUP_GITHUB_TOKEN` | 自动备份使用的 GitHub token |
| `BACKUP_GITHUB_REPO` | 自动备份目标仓库 |
| `BACKUP_INTERVAL_MINUTES` | 自动备份间隔，单位分钟 |
| `CLAPCLAP_AI_MODEL_DIR` | 1.0 AI 部署模型目录，默认 `models/ai/v1/deploy` |
| `CLAPCLAP_AI_INFERENCE_TIMEOUT_MS` | AI 推理超时，默认 100ms |
| `CLAPCLAP_ADMIN_PASSWORD` | 首次创建 UID=0 管理员时使用的初始密码；生产环境必须设置 |

如果备份变量未配置，备份功能会自动禁用。

## 部署

生产启动命令：

```bash
gunicorn server.app:app
```

Railway 部署时建议：

- 挂载持久卷到 `/app/data`
- 设置 `DATA_DIR=/app/data`
- 如需导出接口，设置 `EXPORT_TOKEN`
- 如需自动备份，设置 `BACKUP_GITHUB_TOKEN` 和 `BACKUP_GITHUB_REPO`

Socket.IO 房间功能需要部署平台支持 WebSocket；前端保留 HTTP 轮询兜底。

## 开发约定

- v1 规则代码放在 `app/v1/`
- v2 规则代码放在 `app/v2/`
- 共享能力放在 `app/`、`server/routes/`、`server/static/js/core/`
- 前端 API 优先使用 `/v1/api/...` 或 `/v2/api/...`
- 旧 `/api/...` 入口只作为兼容别名
- 所有需要登录的业务 API 使用 `X-Session-Token`
- AI、训练环境、前端展示都不能绕过规则引擎
- 本地生成文件、训练输出、报告和缓存不要提交

## License

MIT License
