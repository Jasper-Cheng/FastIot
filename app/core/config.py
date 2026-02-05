# app/core/config.py
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import RedisDsn, AmqpDsn, MySQLDsn, validator, Field
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Settings(BaseSettings):
    # 项目信息
    PROJECT_NAME: str = "FastIoT API"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "0.1.0"

    # FastAPI 配置
    DEBUG: bool = True
    HOST: str
    PORT: int
    # 日志配置
    LOG_LEVEL: str = "INFO"
    # 时区配置
    TZ: str

    # 安全配置
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # MySQL 配置
    DATABASE_URL: Optional[MySQLDsn] = None
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_DB: str
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_ROOT_PASSWORD: str

    # Redis 配置
    REDIS_ENABLED: bool = True  # Redis全局开关
    REDIS_URL: Optional[RedisDsn] = None
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: Optional[str] = None

    # RabbitMQ 配置
    RABBITMQ_URL: Optional[AmqpDsn] = None
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str
    RABBITMQ_MANAGEMENT_PORT: int

    # Celery 配置
    CELERY_BROKER_URL: Optional[AmqpDsn] = None
    CELERY_RESULT_BACKEND: Optional[RedisDsn] = None

    # 跨域配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",      # React 默认端口
        "http://localhost:3001",      # React 备用端口
        "http://localhost:8080",      # Vue 默认端口
        "http://localhost:8081",      # Vue 备用端口
        "http://localhost:4200",      # Angular 默认端口
        "http://localhost:5173",      # Vite 默认端口
        "http://localhost:4000",      # 其他前端框架
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "*"                           # 开发环境允许所有来源（生产环境请移除）
    ]

    # 文件上传配置
    MAX_FILE_SIZE: int = 10485760  # 10MB
    UPLOAD_DIR: str = "./uploads"

    # 微信登录配置
    WECHAT_APP_ID: Optional[str] = None
    WECHAT_APP_SECRET: Optional[str] = None
    WECHAT_REDIRECT_URI: Optional[str] = None  # 微信回调地址
    WECHAT_TOKEN: Optional[str] = None  # 微信验证Token（用于URL验证）

    # MQTT 配置（从 .env 读取，变量名：MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD）
    MQTT_HOST: str = None
    MQTT_PORT: int = None
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # 处理字符串格式的CORS_ORIGINS
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 自动生成 DATABASE_URL
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        # 自动生成 REDIS_URL
        if not self.REDIS_URL:
            password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        # 自动生成 RABBITMQ_URL
        if not self.RABBITMQ_URL:
            self.RABBITMQ_URL = f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}//"
        # 自动生成 Celery URL
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.RABBITMQ_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# 全局实例
settings = Settings()