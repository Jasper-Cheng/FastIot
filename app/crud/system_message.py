"""
系统消息CRUD操作
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.db.models.system_message import SystemMessage as SystemMessageModel
from app.models.system_message import SystemMessageCreate, SystemMessageUpdate


async def create_system_message(db: AsyncSession, message_in: SystemMessageCreate) -> SystemMessageModel:
    """创建新的系统消息"""
    db_message = SystemMessageModel(**message_in.model_dump())
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message


async def get_system_message(db: AsyncSession, message_id: int) -> Optional[SystemMessageModel]:
    """根据ID获取系统消息"""
    result = await db.execute(select(SystemMessageModel).where(SystemMessageModel.id == message_id))
    return result.scalar_one_or_none()


async def get_system_messages(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    type: Optional[str] = None,
    priority: Optional[str] = None,
    platform: Optional[str] = None
) -> List[SystemMessageModel]:
    """获取系统消息列表"""
    query = select(SystemMessageModel)
    
    # 添加过滤条件
    conditions = []
    
    if type is not None:
        conditions.append(SystemMessageModel.type == type)
    
    if priority is not None:
        conditions.append(SystemMessageModel.priority == priority)
    
    if platform is not None:
        # 使用JSON_CONTAINS函数检查platforms数组中是否包含指定平台
        conditions.append(
            func.json_contains(
                SystemMessageModel.platforms, 
                f'"{platform}"'
            )
        )
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # 排序：如果updated_at存在则按updated_at排序，不存在则按created_at排序
    query = query.order_by(func.coalesce(SystemMessageModel.updated_at, SystemMessageModel.created_at).desc())
    
    # 分页
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_system_messages_count(
    db: AsyncSession,
    *,
    type: Optional[str] = None,
    priority: Optional[str] = None,
    platform: Optional[str] = None
) -> int:
    """获取系统消息总数"""
    query = select(func.count(SystemMessageModel.id))
    
    # 添加过滤条件
    conditions = []
    
    if type is not None:
        conditions.append(SystemMessageModel.type == type)
    
    if priority is not None:
        conditions.append(SystemMessageModel.priority == priority)
    
    if platform is not None:
        # 使用JSON_CONTAINS函数检查platforms数组中是否包含指定平台
        conditions.append(
            func.json_contains(
                SystemMessageModel.platforms, 
                f'"{platform}"'
            )
        )
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    return result.scalar()


async def update_system_message(
    db: AsyncSession, 
    message_id: int, 
    message_in: SystemMessageUpdate
) -> Optional[SystemMessageModel]:
    """更新系统消息"""
    db_message = await get_system_message(db, message_id)
    if not db_message:
        return None

    update_data = message_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_message, key, value)
    
    await db.commit()
    await db.refresh(db_message)
    return db_message


async def delete_system_message(db: AsyncSession, message_id: int) -> Optional[SystemMessageModel]:
    """删除系统消息"""
    db_message = await get_system_message(db, message_id)
    if not db_message:
        return None
    await db.delete(db_message)
    await db.commit()
    return db_message
