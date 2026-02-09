# FastIoT 物联网设备管理平台

FastIoT 是面向物联网设备的后端管理平台，提供账号与家庭、设备与物模型、签到积分、反馈与系统消息等能力，支持 **RSA+密码** 客户端登录、**MQTT** 设备接入与 **WebSocket** 实时推送。基于 **FastAPI**、**MySQL**、**Redis**、**RabbitMQ** 与 **Docker** 构建。

## 核心功能

### 账号与家庭
- **账号**：统一账号表，角色为 `user` / `admin`
- **家庭**：家庭/组织容器，邀请码、成员管理
- **家庭成员**：账号与家庭多对多，角色 creator/member

### 设备与物模型
- **物模型**：设备功能定义（属性 / 服务 / 事件，JSON）
- **设备型号**：关联物模型，型号代码、厂商
- **设备**：设备实例，序列号、蓝牙名、状态（未绑定/已绑定/离线/在线等）
- **设备网络**：设备网络信息（IP、MAC、WiFi、MQTT 等）
- **设备消息**：设备产生的消息与状态（含 LWT）

### 客户端能力
- **签到**：每日签到、连续天数、积分
- **积分**：积分变动记录与余额
- **系统消息**：通知/公告/告警等
- **版本信息**：多平台版本与强制更新
- **意见反馈**：提交与处理状态

### 实时与通信
- **MQTT**：设备数据/状态主题订阅，按型号分发（如 M701001）
- **WebSocket**：实时推送
- **Redis**：缓存

## 技术栈

| 类别     | 技术 |
|----------|------|
| 后端     | Python 3.9+, FastAPI, Uvicorn |
| 数据库   | MySQL 8.0，SQLAlchemy 2（async + aiomysql） |
| 缓存     | Redis 7 |
| 消息队列 | RabbitMQ 3（可选） |
| 实时     | WebSocket, MQTT（gmqtt） |
| 认证     | JWT, RSA 加密传输密码, Passlib/bcrypt |
| 配置     | pydantic-settings, .env |
| 容器     | Docker, Docker Compose |
| 依赖     | Poetry |

## 项目结构

```
FastIoT/
├── .dockerignore          # 构建忽略（含 .env，避免覆盖运行时注入）
├── .env.example            # 环境变量示例
├── .github/workflows/      # CI（如 Docker 镜像构建）
├── app/
│   ├── api/                # API 层
│   │   ├── admin/          # 管理端：账号、设备、物模型、反馈、日志、通知、版本、积分等
│   │   ├── client/         # 客户端：认证、设备、家庭、签到、积分、系统消息、版本、反馈、WebSocket
│   │   ├── dependencies.py # 依赖注入与认证
│   │   ├── router.py       # 路由汇总（/api/v1/client、/api/v1/admin）
│   │   └── utils.py
│   ├── core/               # 配置、RSA、JWT/密码
│   ├── crud/               # 数据库操作
│   ├── db/                 # 会话、init_db、init.sql、models
│   ├── models/             # Pydantic 请求/响应模型
│   ├── services/           # MQTT、Redis、WebSocket、微信
│   ├── utils/
│   └── main.py             # FastAPI 入口
├── docker-compose.yml      # MySQL / Redis / RabbitMQ / app
├── Dockerfile
├── pyproject.toml
├── poetry.lock
├── project_structure.txt   # 详细结构说明
└── README.md
```

## 快速开始

### 环境要求

- Docker & Docker Compose  
- 本机开发时：Python 3.9+、Poetry

### 1. 克隆与配置

```bash
git clone <repository-url>
cd FastIoT
cp .env.example .env
# 编辑 .env：当前仓库 .env 面向 Docker 环境（mysql/redis/rabbitmq 服务名）
```

### 2. 使用 Docker Compose（推荐）

`.env` 中为 **Docker 环境** 配置：`MYSQL_HOST=mysql`、`REDIS_HOST=redis`、`RABBITMQ_HOST=rabbitmq`，MySQL 容器内端口 3306，宿主机映射端口使用 `MYSQL_HOST_PORT`（如 3307）避免与本地 MySQL 冲突。

```bash
docker-compose up -d
```

- **MySQL**：首次启动时自动执行 `app/db/init.sql` 建库建表并写入默认管理员（如手机 13800000000，密码见 init.sql）。
- **App**：通过 `env_file: .env` 注入环境变量；镜像构建时 `.dockerignore` 已排除 `.env`，避免使用到构建时的旧配置。
- **MQTT**：若 broker 在宿主机，`.env` 中 `MQTT_HOST=host.docker.internal`，需 compose 中配置 `extra_hosts: host.docker.internal:host-gateway`（已包含）。

### 3. 本机直接运行（不用 Docker 跑 app）

若在本机用 Poetry 跑应用，需在 `.env` 中改为本机地址（如 `MYSQL_HOST=localhost`、`MYSQL_PORT=3307`、`REDIS_HOST=localhost` 等），并确保 MySQL/Redis 已启动（可用 Docker 只起中间件）。

```bash
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 数据库初始化（可选）

Docker 下通常已通过 `init.sql` 完成建表。若需用脚本重建或填充种子数据：

```bash
# 仅初始化（不删表）
poetry run python -m app.db.init_db

# 重置并初始化（删表后重建）
poetry run python -m app.db.init_db --reset
```

### 5. 验证

- API 文档：http://localhost:8000/docs  
- ReDoc：http://localhost:8000/redoc  

## 环境变量说明（.env）

| 变量 | 说明 | Docker 示例 |
|------|------|-------------|
| DATABASE_URL | 数据库连接串 | `mysql+aiomysql://用户:密码@mysql:3306/iot` |
| MYSQL_HOST / MYSQL_PORT | 应用连接 MySQL 的主机与端口 | `mysql` / `3306` |
| MYSQL_HOST_PORT | 宿主机映射 MySQL 端口（compose ports） | `3307` |
| REDIS_HOST / REDIS_PORT | Redis | `redis` / `6379` |
| RABBITMQ_HOST / RABBITMQ_PORT | RabbitMQ | `rabbitmq` / `5672` |
| MQTT_HOST / MQTT_PORT | MQTT Broker（宿主机时用 host.docker.internal） | `host.docker.internal` / `1883` |
| SECRET_KEY / ACCESS_TOKEN_EXPIRE_MINUTES | JWT | - |

详见 `.env.example`。

## API 概览

- 前缀：`/api/v1`
- **客户端**：`/api/v1/client` — 认证、设备、家庭、家庭成员、设备消息、签到、积分、系统消息、版本信息、反馈、WebSocket
- **管理端**：`/api/v1/admin` — 认证、账号、设备、设备网络、设备消息、用户、家庭、反馈、操作日志、通知、版本、设备型号、物模型、积分

认证示例（客户端）：
- `GET /api/v1/client/auth/rsa_public_key` — 获取 RSA 公钥
- `POST /api/v1/client/auth/login` — 登录（需先 RSA 加密密码）

完整路径以 Swagger/ReDoc 为准。

## 数据库设计概要

- **account**：账号（手机/邮箱、角色 user|admin、当前家庭等）
- **family**：家庭（名称、邀请码等）
- **family_member**：家庭成员（家庭–账号多对多）
- **device_thing_model**：物模型（属性/服务/事件 JSON）
- **device_model**：设备型号（关联物模型）
- **device**：设备实例（序列号、状态、所属账号等）
- **family_device**：家庭–设备多对多
- **device_message**：设备消息
- **device_network**：设备网络信息（按 device sn 一对一）
- **check_in**：签到记录
- **points**：积分流水
- **system_message**：系统消息
- **version_info**：版本信息
- **feedback**：意见反馈
- **user_operation_log**：用户操作日志

建表与默认数据见 `app/db/init.sql`。

## Docker 部署

```bash
# 构建并启动（app 会使用 .env 中的 Docker 配置）
docker-compose up -d --build

# 仅重建 app 并启动
docker-compose up -d --build --force-recreate app

# 查看日志
docker-compose logs -f app
```

宿主机需开放端口：`PORT`（默认 8000）、`MYSQL_HOST_PORT`（如 3307）、Redis/RabbitMQ 端口等（见 `.env`）。

## 开发说明

- 新增接口：在 `app/api/client` 或 `app/api/admin` 增加模块，在 `app/api/router.py` 中注册。
- 数据库变更：可改 `app/db/init.sql` 与 `app/db/models/`，必要时运行 `python -m app.db.init_db --reset`（注意会清库）。
- 代码风格：项目使用 Black、Ruff 等（见 `pyproject.toml`）。

## 许可证与支持

- 许可证：MIT（见 [LICENSE](LICENSE)）
- 问题与建议：请通过仓库 Issues 反馈。

---

**FastIoT** — 物联网设备管理后端
