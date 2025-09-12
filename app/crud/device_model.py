from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.device_model import DeviceModel
from app.models.device_model import DeviceModelCreate, DeviceModelUpdate
from typing import Optional, List

async def get_device_model(db: AsyncSession, model_id: int) -> Optional[DeviceModel]:
    """根据ID获取设备型号"""
    result = await db.execute(select(DeviceModel).filter(DeviceModel.id == model_id))
    return result.scalar_one_or_none()

async def get_device_models(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DeviceModel]:
    """获取所有设备型号"""
    result = await db.execute(
        select(DeviceModel).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_device_models_by_vendor(db: AsyncSession, vendor: str, skip: int = 0, limit: int = 100) -> List[DeviceModel]:
    """根据厂商获取设备型号"""
    result = await db.execute(
        select(DeviceModel).filter(DeviceModel.vendor == vendor).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create_device_model(db: AsyncSession, model: DeviceModelCreate) -> DeviceModel:
    """创建设备型号"""
    db_model = DeviceModel(
        model_name=model.model_name,
        vendor=model.vendor,
        params=model.params
    )
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def update_device_model(db: AsyncSession, model_id: int, model: DeviceModelUpdate) -> Optional[DeviceModel]:
    """更新设备型号"""
    db_model = await get_device_model(db, model_id)
    if not db_model:
        return None
    
    update_data = model.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_model, field, value)
    
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def delete_device_model(db: AsyncSession, model_id: int) -> bool:
    """删除设备型号"""
    db_model = await get_device_model(db, model_id)
    if not db_model:
        return False
    
    await db.delete(db_model)
    await db.commit()
    return True
