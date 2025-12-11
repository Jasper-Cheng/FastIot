from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List, Tuple
from app.db.models.device_thing_model import DeviceThingModel
from app.db.models.device_model import DeviceModel
from app.db.models.device import Device

async def get_thing_model(db: AsyncSession, thing_model_id: int) -> Optional[DeviceThingModel]:
    """根据ID获取物模型"""
    result = await db.execute(select(DeviceThingModel).filter(DeviceThingModel.id == thing_model_id))
    return result.scalar_one_or_none()

async def get_thing_models_with_pagination(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    name: Optional[str] = None
) -> Tuple[List[DeviceThingModel], int]:
    """获取物模型列表（支持分页和搜索）"""
    query = select(DeviceThingModel)
    count_query = select(func.count(DeviceThingModel.id))
    
    # 构建搜索条件
    conditions = []
    if name:
        conditions.append(DeviceThingModel.name.like(f"%{name}%"))
    
    if conditions:
        query = query.filter(or_(*conditions))
        count_query = count_query.filter(or_(*conditions))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据
    result = await db.execute(query.offset(skip).limit(limit))
    models = result.scalars().all()
    
    return models, total

async def create_thing_model(db: AsyncSession, model_data: dict) -> DeviceThingModel:
    """创建物模型"""
    db_model = DeviceThingModel(
        name=model_data["name"],
        description=model_data.get("description"),
        properties=model_data.get("properties", {}),
        services=model_data.get("services", []),
        events=model_data.get("events", []),
    )
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def update_thing_model(db: AsyncSession, thing_model_id: int, model_data: dict) -> Optional[DeviceThingModel]:
    """更新物模型"""
    db_model = await get_thing_model(db, thing_model_id)
    if not db_model:
        return None
    
    if "name" in model_data:
        db_model.name = model_data["name"]
    if "description" in model_data:
        db_model.description = model_data["description"]
    if "properties" in model_data:
        db_model.properties = model_data["properties"]
    if "services" in model_data:
        db_model.services = model_data["services"]
    if "events" in model_data:
        db_model.events = model_data["events"]
    
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def delete_thing_model(db: AsyncSession, thing_model_id: int) -> bool:
    """删除物模型"""
    db_model = await get_thing_model(db, thing_model_id)
    if not db_model:
        return False
    
    # 检查是否有设备型号使用该物模型
    model_count_result = await db.execute(
        select(func.count(DeviceModel.id)).filter(DeviceModel.thing_model_id == thing_model_id)
    )
    model_count = model_count_result.scalar() or 0
    if model_count > 0:
        raise ValueError(f"有 {model_count} 个设备型号使用该物模型，无法删除")
    
    await db.delete(db_model)
    await db.commit()
    return True

async def count_devices_by_thing_model(db: AsyncSession, thing_model_id: int) -> int:
    """统计使用该物模型的设备数"""
    # 先获取使用该物模型的设备型号
    models_result = await db.execute(
        select(DeviceModel.id).filter(DeviceModel.thing_model_id == thing_model_id)
    )
    model_ids = [row[0] for row in models_result.all()]
    
    if not model_ids:
        return 0
    
    # 统计使用这些型号的设备数
    result = await db.execute(
        select(func.count(Device.id)).filter(Device.model_id.in_(model_ids))
    )
    return result.scalar() or 0

