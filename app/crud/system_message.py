"""
系统消息CRUD操作
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.db.models.system_message import SystemMessage as SystemMessageModel
from app.models.system_message import SystemMessageCreate, SystemMessageUpdate, Platform
from app.crud.base import CRUDBase


class CRUDSystemMessage(CRUDBase[SystemMessageModel, SystemMessageCreate, SystemMessageUpdate]):
    """系统消息CRUD操作类"""
    
    async def get_by_id(self, db: AsyncSession, *, id: int) -> Optional[SystemMessageModel]:
        """根据ID获取系统消息"""
        result = await db.execute(select(SystemMessageModel).where(SystemMessageModel.id == id))
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        type: Optional[str] = None,
        priority: Optional[str] = None,
        platform: Optional[Platform] = None
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
                    f'"{platform.value}"'
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # 排序：按创建时间倒序
        query = query.order_by(SystemMessageModel.created_at.desc())
        
        # 分页
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_count(
        self,
        db: AsyncSession,
        *,
        type: Optional[str] = None,
        priority: Optional[str] = None,
        platform: Optional[Platform] = None
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
                    f'"{platform.value}"'
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        return result.scalar()
    
    async def get_by_platform(
        self,
        db: AsyncSession,
        *,
        platform: Platform,
        skip: int = 0,
        limit: int = 100
    ) -> List[SystemMessageModel]:
        """根据平台获取消息"""
        return await self.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            platform=platform
        )
    
    async def get_latest_messages(
        self,
        db: AsyncSession,
        *,
        platform: Optional[Platform] = None,
        limit: int = 10
    ) -> List[SystemMessageModel]:
        """获取最新消息"""
        return await self.get_multi(
            db=db,
            skip=0,
            limit=limit,
            platform=platform
        )


# 创建CRUD实例
system_message = CRUDSystemMessage(SystemMessageModel)
