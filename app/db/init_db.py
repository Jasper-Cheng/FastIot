import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine
from app.db.models.user import User
from app.db.models.device import Device
from app.core.security import get_password_hash

async def init_db() -> None:
    """初始化数据库"""
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
    
    # 插入初始数据
    async with AsyncSession(engine) as session:
        await insert_initial_data(session)

async def insert_initial_data(session: AsyncSession) -> None:
    """插入初始数据"""
    # 检查是否已有数据
    result = await session.execute(text("SELECT COUNT(*) FROM User"))
    count = result.scalar()
    
    if count == 0:
        # 创建默认管理员用户
        admin_user = User(
            username="admin",
            email="admin@fastiot.com",
            password=get_password_hash("admin123"),
            role="admin"
        )
        session.add(admin_user)
        await session.flush()  # 获取admin用户的ID
        
        # 创建示例设备
        devices = [
            Device(
                name="温度传感器-01",
                serial_number="TEMP001",
                owner_id=admin_user.id,
                status="offline"
            ),
            Device(
                name="湿度传感器-01",
                serial_number="HUM001",
                owner_id=admin_user.id,
                status="offline"
            ),
            Device(
                name="环境监测器-01",
                serial_number="ENV001",
                owner_id=admin_user.id,
                status="offline"
            )
        ]
        
        for device in devices:
            session.add(device)
        
        await session.commit()
        print("数据库初始化完成！")
    else:
        print("数据库已存在数据，跳过初始化")

if __name__ == "__main__":
    asyncio.run(init_db())
