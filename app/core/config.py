# app/core/config.py
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import RedisDsn, AmqpDsn, MySQLDsn

class Settings(BaseSettings):
    # 项目信息
    PROJECT_NAME: str = "FastIot API"
    API_V1_STR: str = "/api/v1"

    # 安全配置
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # MySQL 配置
    DATABASE_URL: Optional[MySQLDsn] = None
    MYSQL_HOST: str
    MYSQL_PORT: int = 3306
    MYSQL_DB: str
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_ROOT_PASSWORD: str

    # Redis 配置
    REDIS_URL: Optional[RedisDsn] = None
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # RabbitMQ 配置
    RABBITMQ_URL: Optional[AmqpDsn] = None
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    # FastAPI 配置
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Celery 配置
    CELERY_BROKER_URL: Optional[AmqpDsn] = None
    CELERY_RESULT_BACKEND: Optional[RedisDsn] = None

    # 日志配置
    LOG_LEVEL: str = "INFO"

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
