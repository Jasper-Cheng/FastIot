from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 创建异步数据库引擎
engine = create_async_engine(
    str(settings.DATABASE_URL).replace('mysql+aiomysql://', 'mysql+aiomysql://'),
    echo=False,  # 关闭SQL语句输出
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "init_command": "SET time_zone = '+08:00'"
    }
)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncSession:
    """获取数据库会话的依赖函数"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
