from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.device_param import DeviceParam
from app.models.device_param import DeviceParamCreate, DeviceParamUpdate
from typing import Optional, List

async def get_device_param(db: AsyncSession, param_id: int) -> Optional[DeviceParam]:
    """根据ID获取设备参数"""
    result = await db.execute(select(DeviceParam).filter(DeviceParam.id == param_id))
    return result.scalar_one_or_none()

async def get_device_param_by_device(db: AsyncSession, device_id: int) -> Optional[DeviceParam]:
    """根据设备ID获取设备参数"""
    result = await db.execute(select(DeviceParam).filter(DeviceParam.device_id == device_id))
    return result.scalar_one_or_none()

async def create_device_param(db: AsyncSession, param: DeviceParamCreate) -> DeviceParam:
    """创建设备参数"""
    db_param = DeviceParam(
        device_id=param.device_id,
        params=param.params
    )
    db.add(db_param)
    await db.commit()
    await db.refresh(db_param)
    return db_param

async def update_device_param(db: AsyncSession, param_id: int, param: DeviceParamUpdate) -> Optional[DeviceParam]:
    """更新设备参数"""
    db_param = await get_device_param(db, param_id)
    if not db_param:
        return None
    
    update_data = param.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_param, field, value)
    
    await db.commit()
    await db.refresh(db_param)
    return db_param

async def update_or_create_device_param(db: AsyncSession, device_id: int, params: dict) -> DeviceParam:
    """更新或创建设备参数"""
    existing_param = await get_device_param_by_device(db, device_id)
    
    if existing_param:
        # 更新现有参数
        existing_param.params = params
        await db.commit()
        await db.refresh(existing_param)
        return existing_param
    else:
        # 创建新参数
        new_param = DeviceParam(
            device_id=device_id,
            params=params
        )
        db.add(new_param)
        await db.commit()
        await db.refresh(new_param)
        return new_param
