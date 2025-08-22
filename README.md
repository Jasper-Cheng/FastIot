# FastIot 后端

FastIot 是一个物联网（IoT）设备管理平台的后端服务，基于 **FastAPI**、**MySQL**、**Redis**、**RabbitMQ** 和 **Celery** 构建。

## 功能

- 设备管理（CRUD）
- 传感器数据接收与存储
- 用户认证与权限控制
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
