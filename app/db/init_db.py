import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine
from app.db.models.user import User
from app.db.models.device import Device
from app.db.models.device_model import DeviceModel
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
    result = await session.execute(text("SELECT COUNT(*) FROM user"))
    count = result.scalar()
    
    if count == 0:
        # 创建默认管理员用户
        admin_user = User(
            username="admin",
            email="admin@fastiot.com",
            password=get_password_hash("admin123")
        )
        session.add(admin_user)
        await session.flush()  # 获取admin用户的ID
        
        # 创建示例设备型号
        device_models = [
            DeviceModel(
                model_name="温度传感器",
                vendor="IoT Corp",
                params={"temperature": {"type": "float", "unit": "°C", "min": -40, "max": 85}}
            ),
            DeviceModel(
                model_name="湿度传感器",
                vendor="IoT Corp",
                params={"humidity": {"type": "float", "unit": "%", "min": 0, "max": 100}}
            ),
            DeviceModel(
                model_name="环境监测器",
                vendor="Smart Devices",
                params={"temperature": {"type": "float", "unit": "°C"}, "humidity": {"type": "float", "unit": "%"}, "pressure": {"type": "float", "unit": "hPa"}}
            )
        ]
        
        for model in device_models:
            session.add(model)
        await session.flush()  # 获取设备型号的ID
        
        # 创建示例设备
        devices = [
            Device(
                name="温度传感器-01",
                sn="TEMP001",
                user_id=admin_user.id,
                model_id=device_models[0].id,
                status="offline"
            ),
            Device(
                name="湿度传感器-01",
                sn="HUM001",
                user_id=admin_user.id,
                model_id=device_models[1].id,
                status="offline"
            ),
            Device(
                name="环境监测器-01",
                sn="ENV001",
                user_id=admin_user.id,
                model_id=device_models[2].id,
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
