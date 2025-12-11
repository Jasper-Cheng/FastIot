from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List, Tuple
from app.db.models.device_model import DeviceModel
from app.db.models.device import Device

async def get_device_model(db: AsyncSession, model_id: int) -> Optional[DeviceModel]:
    """根据ID获取设备型号"""
    result = await db.execute(select(DeviceModel).filter(DeviceModel.id == model_id))
    return result.scalar_one_or_none()

async def get_device_model_by_code(db: AsyncSession, code: str) -> Optional[DeviceModel]:
    """根据型号代码获取设备型号"""
    result = await db.execute(select(DeviceModel).filter(DeviceModel.model_code == code))
    return result.scalar_one_or_none()

async def get_device_models_with_pagination(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    name: Optional[str] = None,
    code: Optional[str] = None,
    manufacturer: Optional[str] = None,
    thing_model_id: Optional[int] = None,
    status: Optional[str] = None
) -> Tuple[List[DeviceModel], int]:
    """获取设备型号列表（支持分页和搜索）"""
    query = select(DeviceModel)
    count_query = select(func.count(DeviceModel.id))
    
    # 构建搜索条件
    conditions = []
    if name:
        conditions.append(DeviceModel.name.like(f"%{name}%"))
    if code:
        conditions.append(DeviceModel.model_code.like(f"%{code}%"))
    if manufacturer:
        conditions.append(DeviceModel.vendor.like(f"%{manufacturer}%"))
    if thing_model_id:
        conditions.append(DeviceModel.thing_model_id == thing_model_id)
    # status 字段在数据库模型中不存在，暂时忽略
    
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

async def get_all_device_models(db: AsyncSession) -> List[DeviceModel]:
    """获取所有设备型号（用于下拉选择）"""
    result = await db.execute(select(DeviceModel))
    return result.scalars().all()

async def create_device_model(db: AsyncSession, model_data: dict) -> DeviceModel:
    """创建设备型号"""
    db_model = DeviceModel(
        model_code=model_data["code"],
        name=model_data["name"],
        vendor=model_data.get("manufacturer"),
        thing_model_id=model_data["thingModelId"],
        properties=model_data.get("properties", {}),
        services=model_data.get("services", []),
        events=model_data.get("events", []),
    )
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def update_device_model(db: AsyncSession, model_id: int, model_data: dict) -> Optional[DeviceModel]:
    """更新设备型号"""
    db_model = await get_device_model(db, model_id)
    if not db_model:
        return None
    
    if "code" in model_data:
        db_model.model_code = model_data["code"]
    if "name" in model_data:
        db_model.name = model_data["name"]
    if "manufacturer" in model_data:
        db_model.vendor = model_data["manufacturer"]
    if "thingModelId" in model_data:
        db_model.thing_model_id = model_data["thingModelId"]
    if "properties" in model_data:
        db_model.properties = model_data["properties"]
    if "services" in model_data:
        db_model.services = model_data["services"]
    if "events" in model_data:
        db_model.events = model_data["events"]
    
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def delete_device_model(db: AsyncSession, model_id: int) -> bool:
    """删除设备型号"""
    db_model = await get_device_model(db, model_id)
    if not db_model:
        return False
    
    # 检查是否有设备使用该型号
    device_count_result = await db.execute(
        select(func.count(Device.id)).filter(Device.model_id == model_id)
    )
    device_count = device_count_result.scalar() or 0
    if device_count > 0:
        raise ValueError(f"有 {device_count} 个设备使用该型号，无法删除")
    
    await db.delete(db_model)
    await db.commit()
    return True

async def count_devices_by_model(db: AsyncSession, model_id: int) -> int:
    """统计使用该型号的设备数"""
    result = await db.execute(
        select(func.count(Device.id)).filter(Device.model_id == model_id)
    )
    return result.scalar() or 0

