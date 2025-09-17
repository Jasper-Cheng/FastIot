# FastIoT 物联网设备管理平台

FastIoT 是一个完整的物联网（IoT）设备管理平台，提供设备管理、用户管理、实时通信、告警系统等核心功能。基于 **FastAPI**、**MySQL**、**Redis** 和 **WebSocket** 构建。

## 🚀 核心功能

### 用户管理
- **账号系统**: 支持多种角色（用户、成员、管理员）
- **用户管理**: 完整的用户生命周期管理
- **成员管理**: 支持家庭成员和设备共享
- **权限管理**: 简化的权限控制（已移除复杂RBAC）

### 设备管理
- **设备注册**: 支持设备型号、序列号管理
- **设备绑定**: 设备与用户的绑定/解绑
- **设备网络**: 设备网络状态监控（WiFi、蓝牙、蜂窝等）
- **设备日志**: 设备操作和事件日志记录
- **设备参数**: 设备配置参数管理
- **物模型**: 设备功能定义和标准化

### 房间管理
- **房间管理**: 房间创建、编辑、删除
- **设备分组**: 设备按房间分组管理
- **智能排序**: 房间内设备排序功能

### 告警系统
- **实时告警**: 设备状态异常告警
- **告警分级**: 支持不同级别的告警
- **告警统计**: 告警数据统计和分析
- **批量操作**: 支持批量标记已读

### 实时通信
- **WebSocket**: 实时设备状态推送
- **MQTT**: 物联网设备通信协议
- **Redis**: 缓存和消息队列

## 🛠 技术栈

- **后端框架**: Python 3.9+, FastAPI
- **数据库**: MySQL 8.0+ (使用 aiomysql 异步驱动)
- **缓存**: Redis 6.0+
- **消息队列**: Redis (替代 RabbitMQ)
- **实时通信**: WebSocket, MQTT
- **容器化**: Docker + docker-compose
- **依赖管理**: Poetry
- **API文档**: Swagger UI / ReDoc

## 📁 项目结构

```
FastIoT/
├── app/
│   ├── api/                    # API接口层
│   │   ├── endpoints/          # 各功能模块端点
│   │   ├── dependencies.py     # 依赖注入和认证
│   │   └── router.py          # 路由配置
│   ├── core/                  # 核心配置
│   ├── crud/                  # 数据库操作层
│   ├── db/                    # 数据库模块
│   │   ├── models/            # SQLAlchemy模型
│   │   └── init_db.py         # 数据库初始化
│   ├── models/                # Pydantic模型
│   ├── services/              # 业务逻辑服务
│   ├── main.py               # 应用入口
│   └── worker.py             # 后台任务
├── docker-compose.yml         # 容器编排
├── Dockerfile                 # 镜像构建
└── pyproject.toml            # 项目配置
```

## 🚀 快速启动

### 1. 环境准备

确保已安装以下软件：
- Python 3.9+
- Poetry
- Docker & Docker Compose
- MySQL 8.0+
- Redis 6.0+

### 2. 克隆项目

```bash
git clone <repository-url>
cd FastIoT
```

### 3. 安装依赖

```bash
poetry install
```

### 4. 配置环境变量

创建 `.env` 文件：

```env
# 数据库配置
DATABASE_URL=mysql+aiomysql://username:password@localhost:3306/fastiot
MYSQL_ROOT_PASSWORD=your_password

# Redis配置
REDIS_URL=redis://localhost:6379/0

# JWT配置
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# MQTT配置
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
```

### 5. 启动服务

#### 使用 Docker Compose（推荐）

```bash
docker-compose up -d
```

#### 手动启动

```bash
# 启动数据库
docker run -d --name mysql -e MYSQL_ROOT_PASSWORD=password -p 3306:3306 mysql:8.0

# 启动Redis
docker run -d --name redis -p 6379:6379 redis:6.0

# 初始化数据库
python app/db/init_db.py

# 启动应用
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 验证安装

访问以下地址验证服务：

- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health

## 🗄️ 数据库设计

### 核心实体关系

FastIoT 平台采用关系型数据库设计，主要包含以下核心实体：

#### 用户体系
- **account**: 统一账号表，支持多种角色（owner/member/admin）
- **user**: 主用户表，与 account 一对一关联
- **member**: 成员表，属于某个 user，与 account 一对一关联
- **admin**: 管理员表，与 account 一对一关联

#### 设备体系
- **thing_model**: 物模型表，定义设备功能能力
- **device_model**: 设备型号表，关联物模型
- **device**: 设备实例表，关联设备型号和用户
- **device_network**: 设备网络信息表，与设备一对一关联
- **device_param**: 设备参数表，存储设备实时参数
- **device_log**: 设备日志表，记录设备运行历史

#### 空间管理
- **room**: 房间表，属于某个用户
- **room_device**: 房间设备关联表，多对多关系

#### 权限与告警
- **member_device_permission**: 成员设备权限表
- **alert**: 告警表，关联设备

### 实体关系图 (ER Diagram)

```mermaid
erDiagram
    ACCOUNT ||--o| USER : "1:1"
    ACCOUNT ||--o| MEMBER : "1:1"
    ACCOUNT ||--o| ADMIN : "1:1"
    
    USER ||--o{ MEMBER : "1:N"
    USER ||--o{ ROOM : "1:N"
    USER ||--o{ DEVICE : "1:N"
    
    THING_MODEL ||--o{ DEVICE_MODEL : "1:N"
    DEVICE_MODEL ||--o{ DEVICE : "1:N"
    
    DEVICE ||--|| DEVICE_NETWORK : "1:1"
    DEVICE ||--o| DEVICE_PARAM : "1:1"
    DEVICE ||--o{ DEVICE_LOG : "1:N"
    DEVICE ||--o{ ALERT : "1:N"
    
    ROOM ||--o{ ROOM_DEVICE : "1:N"
    DEVICE ||--o{ ROOM_DEVICE : "1:N"
    
    MEMBER ||--o{ MEMBER_DEVICE_PERMISSION : "1:N"
    DEVICE ||--o{ MEMBER_DEVICE_PERMISSION : "1:N"
    
    ACCOUNT {
        bigint id PK
        varchar account UK
        varchar password_hash
        varchar name
        enum gender
        varchar phone UK
        varchar email UK
        varchar avatar
        enum role
        timestamp created_at
    }
    
    USER {
        bigint id PK
        bigint account_id FK
        timestamp created_at
    }
    
    MEMBER {
        bigint id PK
        bigint user_id FK
        bigint account_id FK
        timestamp created_at
    }
    
    ADMIN {
        bigint id PK
        bigint account_id FK
        timestamp created_at
    }
    
    ROOM {
        bigint id PK
        bigint user_id FK
        varchar name
        timestamp created_at
    }
    
    THING_MODEL {
        bigint id PK
        varchar name
        varchar description
        json properties
        json services
        json events
        timestamp created_at
    }
    
    DEVICE_MODEL {
        bigint id PK
        varchar model_code UK
        varchar name
        varchar vendor
        bigint thing_model_id FK
        json params
        timestamp created_at
    }
    
    DEVICE {
        bigint id PK
        bigint user_id FK
        bigint model_id FK
        varchar name
        varchar sn UK
        enum status
        timestamp created_at
    }
    
    DEVICE_NETWORK {
        bigint id PK
        bigint device_id FK
        varchar net_type
        varchar name
        varchar ip
        varchar mac
        int rssi
        tinyint connect_state
        json extra
        timestamp last_update
    }
    
    DEVICE_PARAM {
        bigint id PK
        bigint device_id FK
        json params
        timestamp updated_at
    }
    
    DEVICE_LOG {
        bigint id PK
        bigint device_id FK
        varchar event_type
        json params
        timestamp created_at
    }
    
    ROOM_DEVICE {
        bigint id PK
        bigint room_id FK
        bigint device_id FK
        int sort_order
    }
    
    MEMBER_DEVICE_PERMISSION {
        bigint id PK
        bigint member_id FK
        bigint device_id FK
    }
    
    ALERT {
        bigint id PK
        bigint device_id FK
        enum level
        enum status
        varchar message
        timestamp created_at
    }
```

### 关键关系说明

#### 1. 用户体系关系
- **account** 是核心账号表，所有用户类型都基于此表
- **user** 代表主用户（家庭/组织拥有者）
- **member** 代表子用户，必须属于某个 user
- **admin** 代表系统管理员

#### 2. 设备体系关系
- **thing_model** 定义设备功能标准（属性、服务、事件）
- **device_model** 是具体型号，基于物模型
- **device** 是设备实例，属于某个用户
- **device_network** 存储设备网络状态（一对一）
- **device_param** 存储设备实时参数（一对一）
- **device_log** 记录设备历史事件（一对多）

#### 3. 空间管理关系
- **room** 属于某个用户
- **room_device** 实现房间与设备的多对多关系

#### 4. 权限控制关系
- **member_device_permission** 控制成员对设备的访问权限
- 存在记录即表示有权限

#### 5. 告警系统关系
- **alert** 关联设备，记录设备产生的告警

### 数据库特性

- **字符集**: utf8mb4_unicode_ci，支持完整 Unicode
- **存储引擎**: InnoDB，支持事务和外键约束
- **索引优化**: 主键、唯一键、外键索引
- **级联删除**: 合理的级联删除策略
- **JSON 字段**: 灵活存储复杂数据结构
- **时间戳**: 自动记录创建和更新时间

## 📚 API 文档

### 认证端点
- `POST /api/v1/auth/login/form` - 表单登录
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/refresh` - 刷新令牌

### 用户管理
- `GET /api/v1/users/` - 获取用户列表
- `GET /api/v1/users/{user_id}` - 获取用户详情
- `DELETE /api/v1/users/{user_id}` - 删除用户

### 设备管理
- `GET /api/v1/devices/` - 获取设备列表
- `POST /api/v1/devices/` - 创建设备
- `GET /api/v1/devices/{device_id}` - 获取设备详情
- `PUT /api/v1/devices/{device_id}` - 更新设备
- `DELETE /api/v1/devices/{device_id}` - 删除设备
- `POST /api/v1/devices/{device_id}/bind` - 绑定设备
- `POST /api/v1/devices/{device_id}/unbind` - 解绑设备

### 房间管理
- `GET /api/v1/rooms/` - 获取房间列表
- `POST /api/v1/rooms/` - 创建房间
- `GET /api/v1/rooms/{room_id}` - 获取房间详情
- `PUT /api/v1/rooms/{room_id}` - 更新房间
- `DELETE /api/v1/rooms/{room_id}` - 删除房间

### 告警管理
- `GET /api/v1/alerts/` - 获取告警列表
- `POST /api/v1/alerts/` - 创建告警
- `GET /api/v1/alerts/{alert_id}` - 获取告警详情
- `PUT /api/v1/alerts/{alert_id}` - 更新告警
- `DELETE /api/v1/alerts/{alert_id}` - 删除告警
- `POST /api/v1/alerts/user/{user_id}/mark-all-read` - 标记所有告警为已读

## 🔧 开发指南

### 添加新的API端点

1. 在 `app/api/endpoints/` 创建新的端点文件
2. 在 `app/crud/` 添加对应的CRUD操作
3. 在 `app/models/` 添加Pydantic模型
4. 在 `app/db/models/` 添加SQLAlchemy模型
5. 在 `app/api/router.py` 注册路由

### 数据库迁移

```bash
# 重置数据库
python app/db/init_db.py
```

### 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行特定测试
poetry run pytest tests/test_devices.py
```

## 🔒 权限说明

**注意**: 当前版本已移除复杂的基于角色的访问控制（RBAC）。所有认证用户都可以访问所有API端点。仅保留基本的资源存在性验证。

如需重新启用权限控制，请参考项目历史提交记录。

## 📋 待办事项 (TODO)

### 🔐 权限控制
- [ ] 重新实现基于角色的访问控制 (RBAC)
- [ ] 添加资源所有权验证
- [ ] 实现细粒度权限控制
- [ ] 添加权限管理界面
- [ ] 实现权限继承机制

### 🚀 Redis 缓存
- [ ] 实现设备状态缓存
- [ ] 添加用户会话缓存
- [ ] 实现API响应缓存
- [ ] 添加分布式锁机制
- [ ] 实现缓存失效策略
- [ ] 添加缓存监控和统计

### 🔧 系统优化
- [ ] 数据库查询优化
- [ ] API性能监控
- [ ] 日志系统完善
- [ ] 错误处理优化
- [ ] 单元测试覆盖

## 🐳 Docker 部署

### 构建镜像

```bash
docker build -t fastiot:latest .
```

### 运行容器

```bash
docker run -d \
  --name fastiot \
  -p 8000:8000 \
  -e DATABASE_URL=mysql+aiomysql://user:pass@host:3306/db \
  -e REDIS_URL=redis://host:6379/0 \
  fastiot:latest
```

### 使用 Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

如有问题或建议，请：

1. 查看 [Issues](https://github.com/your-repo/issues)
2. 创建新的 Issue
3. 联系维护者

---

**FastIoT** - 让物联网设备管理更简单 🚀