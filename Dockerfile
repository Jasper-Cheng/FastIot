# FastIoT 应用镜像 - 用于 Docker Compose 及 GitHub Actions 自动构建推送
# 构建: docker build -t fastiot-app .  或由 .github/workflows/docker-image.yml 触发
FROM python:3.12-slim

WORKDIR /app

# 安装 Poetry（不创建 venv，依赖装到系统 Python）
RUN pip install --no-cache-dir poetry

# 先只复制依赖声明，便于利用构建缓存
COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi --only main

# 复制应用代码（.dockerignore 已排除 .env，运行时由 compose 注入）
COPY . /app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 非 root 用户运行；预留上传目录
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]