# app/core/config.py
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import RedisDsn, AmqpDsn, MySQLDsn

class Settings(BaseSettings):
    # API
    PROJECT_NAME: str = "FastIot API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-super-secret-key-here"  # 生成: openssl rand -hex 32
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 60 minutes * 24 hours * 8 days = 8 days

    # MySQL
    MYSQL_SERVER: str = "mysql"
    MYSQL_USER: str = "fastiot"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DB: str = "fastiot_db"
    MYSQL_PORT: str = "3306"
    DATABASE_URI: MySQLDsn | None = None

    # Redis
    REDIS_URL: RedisDsn = "redis://redis:6379/0"

    # RabbitMQ (for Celery)
    CELERY_BROKER_URL: AmqpDsn = "amqp://rabbitmq:5672"
    CELERY_RESULT_BACKEND: RedisDsn = "redis://redis:6379/1"

    # MQTT Broker (for device communication)
    MQTT_BROKER_HOST: str = "mqtt-broker"
    MQTT_BROKER_PORT: int = 1883

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 构造数据库URL
        self.DATABASE_URI = Optional[f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{self.MYSQL_DB}"]

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()