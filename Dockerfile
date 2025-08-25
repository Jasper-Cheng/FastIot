# 使用官方 Python 3.13 slim 镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装 Poetry
RUN pip install --no-cache-dir poetry

# 复制依赖文件
COPY pyproject.toml poetry.lock* /app/

# 安装依赖，不创建虚拟环境
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

# 复制整个项目
COPY . /app

# 设置 Python 输出不缓存
ENV PYTHONUNBUFFERED=1

# 默认启动 FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
