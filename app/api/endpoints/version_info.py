from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api.dependencies import get_db, get_current_admin
from app.crud.version_info import version_info
from app.models.version_info import VersionInfo, VersionInfoCreate, VersionInfoUpdate
from app.db.models.admin import Admin

router = APIRouter()


@router.post("/", response_model=VersionInfo)
def create_version_info(
    *,
    db: Session = Depends(get_db),
    version_info_in: VersionInfoCreate,
    current_admin: Admin = Depends(get_current_admin)
):
    """创建版本信息"""
    # 检查版本号是否已存在
    existing_version = version_info.get_by_version_code(db, version_code=version_info_in.version_code)
    if existing_version:
        raise HTTPException(
            status_code=400,
            detail="版本号已存在"
        )
    
    return version_info.create(db=db, obj_in=version_info_in)


@router.get("/", response_model=List[VersionInfo])
def get_version_infos(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    platform: Optional[str] = Query(None),
    order_by: str = Query("created_at"),
    order_desc: bool = Query(True)
):
    """获取版本信息列表"""
    return version_info.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        platform=platform,
        order_by=order_by,
        order_desc=order_desc
    )


@router.get("/latest/{platform}")
def get_latest_version(
    *,
    db: Session = Depends(get_db),
    platform: str
):
    """获取指定平台的最新版本"""
    latest_version = version_info.get_latest_by_platform(db=db, platform=platform)
    if not latest_version:
        raise HTTPException(
            status_code=404,
            detail=f"未找到平台 {platform} 的版本信息"
        )
    return latest_version


@router.get("/{version_id}", response_model=VersionInfo)
def get_version_info(
    *,
    db: Session = Depends(get_db),
    version_id: int
):
    """根据ID获取版本信息"""
    version = version_info.get(db=db, id=version_id)
    if not version:
        raise HTTPException(
            status_code=404,
            detail="版本信息不存在"
        )
    return version


@router.put("/{version_id}", response_model=VersionInfo)
def update_version_info(
    *,
    db: Session = Depends(get_db),
    version_id: int,
    version_info_in: VersionInfoUpdate,
    current_admin: Admin = Depends(get_current_admin)
):
    """更新版本信息"""
    version = version_info.get(db=db, id=version_id)
    if not version:
        raise HTTPException(
            status_code=404,
            detail="版本信息不存在"
        )
    
    # 如果更新版本号，检查是否与其他版本冲突
    if version_info_in.version_code and version_info_in.version_code != version.version_code:
        existing_version = version_info.get_by_version_code(db, version_code=version_info_in.version_code)
        if existing_version:
            raise HTTPException(
                status_code=400,
                detail="版本号已存在"
            )
    
    return version_info.update(db=db, db_obj=version, obj_in=version_info_in)


@router.delete("/{version_id}")
def delete_version_info(
    *,
    db: Session = Depends(get_db),
    version_id: int,
    current_admin: Admin = Depends(get_current_admin)
):
    """删除版本信息"""
    version = version_info.get(db=db, id=version_id)
    if not version:
        raise HTTPException(
            status_code=404,
            detail="版本信息不存在"
        )
    
    version_info.remove(db=db, id=version_id)
    return {"message": "版本信息已删除"}


@router.get("/search/{keyword}")
def search_version_infos(
    *,
    db: Session = Depends(get_db),
    keyword: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """搜索版本信息"""
    return version_info.search(db=db, keyword=keyword, skip=skip, limit=limit)
