from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import List, Optional, Dict, Any
from app.db.models.version_info import VersionInfo
from app.models.version_info import VersionInfoCreate, VersionInfoUpdate


class CRUDVersionInfo:
    def create(self, db: Session, *, obj_in: VersionInfoCreate) -> VersionInfo:
        """创建版本信息"""
        db_obj = VersionInfo(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: int) -> Optional[VersionInfo]:
        """根据ID获取版本信息"""
        return db.query(VersionInfo).filter(VersionInfo.id == id).first()

    def get_by_version_code(self, db: Session, *, version_code: str) -> Optional[VersionInfo]:
        """根据版本号获取版本信息"""
        return db.query(VersionInfo).filter(VersionInfo.version_code == version_code).first()

    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        platform: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[VersionInfo]:
        """获取版本信息列表"""
        query = db.query(VersionInfo)
        
        # 过滤条件
        if platform:
            query = query.filter(VersionInfo.platform == platform)
        
        # 排序
        order_column = getattr(VersionInfo, order_by, VersionInfo.created_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))
        
        return query.offset(skip).limit(limit).all()

    def get_latest_by_platform(self, db: Session, *, platform: str) -> Optional[VersionInfo]:
        """获取指定平台的最新版本"""
        return (
            db.query(VersionInfo)
            .filter(VersionInfo.platform == platform)
            .order_by(desc(VersionInfo.created_at))
            .first()
        )

    def update(self, db: Session, *, db_obj: VersionInfo, obj_in: VersionInfoUpdate) -> VersionInfo:
        """更新版本信息"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> Optional[VersionInfo]:
        """删除版本信息"""
        obj = db.query(VersionInfo).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def search(self, db: Session, *, keyword: str, skip: int = 0, limit: int = 100) -> List[VersionInfo]:
        """搜索版本信息"""
        return (
            db.query(VersionInfo)
            .filter(
                or_(
                    VersionInfo.version_code.contains(keyword),
                    VersionInfo.version_name.contains(keyword),
                    VersionInfo.title.contains(keyword),
                    VersionInfo.description.contains(keyword)
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


version_info = CRUDVersionInfo()
