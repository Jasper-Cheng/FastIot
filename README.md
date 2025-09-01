# FastIot 后端

FastIot 是一个物联网（IoT）设备管理平台的后端服务，基于 **FastAPI**、**MySQL**、**Redis**、**RabbitMQ** 和 **Celery** 构建。

## 功能

- 设备管理（CRUD）
- 传感器数据接收与存储
- 用户认证与权限控制（支持邮箱验证）
- WebSocket 实时通信
- 异步任务处理（Celery + Redis/RabbitMQ）

## 技术栈

- **后端**：Python 3.9+, FastAPI
- **异步任务**：Celery + Redis/RabbitMQ
- **数据库**：MySQL（使用 aiomysql 异步驱动）
- **缓存**：Redis
- **消息队列**：RabbitMQ
- **容器化**：Docker + docker-compose
- **依赖管理**：Poetry

## 快速启动

### 1. 安装依赖

```bash
poetry install
```

### 2. 启动应用

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 测试CORS配置

```bash
python test_cors.py
```

## CORS配置

应用已配置完整的CORS支持，允许以下前端开发端口：

- **React**: `http://localhost:3000`, `http://localhost:3001`
- **Vue**: `http://localhost:8080`, `http://localhost:8081`
- **Angular**: `http://localhost:4200`
- **Vite**: `http://localhost:5173`
- **其他**: `http://localhost:4000`

支持的方法：`GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`, `PATCH`

支持的头：`Authorization`, `Content-Type`, `X-Requested-With` 等

## API文档

启动应用后，访问以下地址查看API文档：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **健康检查**: `http://localhost:8000/health`
