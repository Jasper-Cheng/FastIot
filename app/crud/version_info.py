from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, asc, select
from typing import List, Optional, Dict, Any
from app.db.models.version_info import VersionInfo
from app.models.version_info import VersionInfoCreate, VersionInfoUpdate, PlatformEnum


class CRUDVersionInfo:
    async def create(self, db: AsyncSession, *, obj_in: VersionInfoCreate) -> VersionInfo:
        """创建版本信息"""
        db_obj = VersionInfo(**obj_in.dict())
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, id: int) -> Optional[VersionInfo]:
        """根据ID获取版本信息"""
        result = await db.execute(select(VersionInfo).where(VersionInfo.id == id))
        return result.scalar_one_or_none()

    async def get_by_version_code(self, db: AsyncSession, *, version_code: str, platform: Optional[PlatformEnum] = None) -> Optional[VersionInfo]:
        """根据版本号和平台获取版本信息"""
        query = select(VersionInfo).where(VersionInfo.version_code == version_code)
        if platform:
            query = query.where(VersionInfo.platform == platform.value)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        platform: Optional[PlatformEnum] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[VersionInfo]:
        """获取版本信息列表"""
        query = select(VersionInfo)
        
        # 过滤条件
        if platform:
            query = query.where(VersionInfo.platform == platform.value)
        
        # 排序
        order_column = getattr(VersionInfo, order_by, VersionInfo.created_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_latest_by_platform(self, db: AsyncSession, *, platform: PlatformEnum) -> Optional[VersionInfo]:
        """获取指定平台的最新版本"""
        result = await db.execute(
            select(VersionInfo)
            .where(VersionInfo.platform == platform.value)
            .order_by(desc(VersionInfo.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update(self, db: AsyncSession, *, db_obj: VersionInfo, obj_in: VersionInfoUpdate) -> VersionInfo:
        """更新版本信息"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[VersionInfo]:
        """删除版本信息"""
        result = await db.execute(select(VersionInfo).where(VersionInfo.id == id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def search(self, db: AsyncSession, *, keyword: str, skip: int = 0, limit: int = 100) -> List[VersionInfo]:
        """搜索版本信息"""
        result = await db.execute(
            select(VersionInfo)
            .where(
                or_(
                    VersionInfo.version_code.contains(keyword),
                    VersionInfo.version_name.contains(keyword),
                    VersionInfo.title.contains(keyword),
                    VersionInfo.description.contains(keyword)
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


version_info = CRUDVersionInfo()
