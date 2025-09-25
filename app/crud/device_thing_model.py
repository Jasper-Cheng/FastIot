from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.device_thing_model import DeviceThingModel
from app.models.device_thing_model import DeviceThingModelCreate, DeviceThingModelUpdate
from typing import Optional, List

async def get_device_thing_model(db: AsyncSession, model_id: int) -> Optional[DeviceThingModel]:
    """根据ID获取设备物模型"""
    result = await db.execute(select(DeviceThingModel).filter(DeviceThingModel.id == model_id))
    return result.scalar_one_or_none()

async def get_device_thing_models(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DeviceThingModel]:
    """获取所有设备物模型"""
    result = await db.execute(select(DeviceThingModel).offset(skip).limit(limit))
    return result.scalars().all()

async def create_device_thing_model(db: AsyncSession, model: DeviceThingModelCreate) -> DeviceThingModel:
    """创建设备物模型"""
    db_model = DeviceThingModel(
        name=model.name,
        description=model.description,
        properties=model.properties,
        services=model.services,
        events=model.events
    )
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def update_device_thing_model(db: AsyncSession, model_id: int, model: DeviceThingModelUpdate) -> Optional[DeviceThingModel]:
    """更新设备物模型"""
    db_model = await get_device_thing_model(db, model_id)
    if not db_model:
        return None
    
    update_data = model.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_model, field, value)
    
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def delete_device_thing_model(db: AsyncSession, model_id: int) -> bool:
    """删除设备物模型"""
    db_model = await get_device_thing_model(db, model_id)
    if not db_model:
        return False
    
    await db.delete(db_model)
    await db.commit()
    return True
