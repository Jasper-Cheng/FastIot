# 使用官方 Python 镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY pyproject.toml poetry.lock* /app/
RUN pip install poetry && poetry install --no-root --only main

# 拷贝应用代码
COPY . /app

# 默认启动 FastAPI（docker-compose 中 worker 会覆盖 CMD）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
