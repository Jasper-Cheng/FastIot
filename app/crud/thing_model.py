from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.thing_model import ThingModel
from app.models.thing_model import ThingModelCreate, ThingModelUpdate
from typing import Optional, List

async def get_thing_model(db: AsyncSession, model_id: int) -> Optional[ThingModel]:
    """根据ID获取物模型"""
    result = await db.execute(select(ThingModel).filter(ThingModel.id == model_id))
    return result.scalar_one_or_none()

async def get_thing_models(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[ThingModel]:
    """获取所有物模型"""
    result = await db.execute(select(ThingModel).offset(skip).limit(limit))
    return result.scalars().all()

async def create_thing_model(db: AsyncSession, model: ThingModelCreate) -> ThingModel:
    """创建物模型"""
    db_model = ThingModel(
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

async def update_thing_model(db: AsyncSession, model_id: int, model: ThingModelUpdate) -> Optional[ThingModel]:
    """更新物模型"""
    db_model = await get_thing_model(db, model_id)
    if not db_model:
        return None
    
    update_data = model.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_model, field, value)
    
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def delete_thing_model(db: AsyncSession, model_id: int) -> bool:
    """删除物模型"""
    db_model = await get_thing_model(db, model_id)
    if not db_model:
        return False
    
    await db.delete(db_model)
    await db.commit()
    return True
