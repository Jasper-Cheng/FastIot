from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, func, or_

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.version_info import version_info
from app.db.models.version_info import VersionInfo
from app.models.version_info import VersionInfoCreate, VersionInfoUpdate, PlatformEnum

router = APIRouter()


@router.get("/version/list")
async def get_version_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    versionCode: Optional[str] = Query(None, description="版本号搜索"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取版本列表"""
    skip = (page - 1) * pageSize
    
    # 构建查询
    query = select(VersionInfo)
    count_query = select(func.count(VersionInfo.id))
    
    conditions = []
    if versionCode:
        conditions.append(VersionInfo.version_code.like(f"%{versionCode}%"))
    if platform:
        conditions.append(VersionInfo.platform == platform)
    
    if conditions:
        query = query.filter(or_(*conditions))
        count_query = count_query.filter(or_(*conditions))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据
    result = await db.execute(
        query.order_by(VersionInfo.created_at.desc())
        .offset(skip)
        .limit(pageSize)
    )
    versions = result.scalars().all()
    
    items = []
    for version in versions:
        items.append({
            "id": version.id,
            "versionCode": version.version_code,
            "versionName": version.version_name,
            "platform": version.platform,
            "title": version.title,
            "description": version.description,
            "downloadUrl": version.download_url,
            "fileSize": version.file_size,
            "isForceUpdate": version.is_force_update,
            "minSupportedVersion": version.min_supported_version,
            "extra": version.extra or {},
            "createdAt": version.created_at.strftime("%Y-%m-%d %H:%M:%S") if version.created_at else None,
            "updatedAt": version.updated_at.strftime("%Y-%m-%d %H:%M:%S") if version.updated_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.post("/version")
async def create_version(
    version_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建版本"""
    # 验证必填字段
    if not version_data.get("versionCode"):
        raise HTTPException(status_code=400, detail="版本号不能为空")
    if not version_data.get("versionName"):
        raise HTTPException(status_code=400, detail="版本名称不能为空")
    if not version_data.get("platform"):
        raise HTTPException(status_code=400, detail="平台不能为空")
    if not version_data.get("title"):
        raise HTTPException(status_code=400, detail="标题不能为空")
    if not version_data.get("description"):
        raise HTTPException(status_code=400, detail="描述不能为空")
    
    version_create = VersionInfoCreate(
        version_code=version_data["versionCode"],
        version_name=version_data["versionName"],
        platform=PlatformEnum(version_data["platform"]),
        title=version_data["title"],
        description=version_data["description"],
        download_url=version_data.get("downloadUrl"),
        file_size=version_data.get("fileSize"),
        is_force_update=version_data.get("isForceUpdate", False),
        min_supported_version=version_data.get("minSupportedVersion"),
        extra=version_data.get("extra", {})
    )
    
    version = await version_info.create(db, obj_in=version_create)
    
    return {
        "id": version.id,
        "versionCode": version.version_code,
        "versionName": version.version_name,
        "platform": version.platform,
        "title": version.title,
        "description": version.description,
        "downloadUrl": version.download_url,
        "fileSize": version.file_size,
        "isForceUpdate": version.is_force_update,
        "minSupportedVersion": version.min_supported_version,
        "extra": version.extra or {},
        "createdAt": version.created_at.strftime("%Y-%m-%d %H:%M:%S") if version.created_at else None,
        "updatedAt": version.updated_at.strftime("%Y-%m-%d %H:%M:%S") if version.updated_at else None
    }


@router.put("/version/{id}")
async def update_version(
    id: int,
    version_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新版本"""
    # 验证版本是否存在
    version = await version_info.get(db, id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    version_update = VersionInfoUpdate()
    if "versionCode" in version_data:
        version_update.version_code = version_data["versionCode"]
    if "versionName" in version_data:
        version_update.version_name = version_data["versionName"]
    if "platform" in version_data:
        version_update.platform = PlatformEnum(version_data["platform"])
    if "title" in version_data:
        version_update.title = version_data["title"]
    if "description" in version_data:
        version_update.description = version_data["description"]
    if "downloadUrl" in version_data:
        version_update.download_url = version_data["downloadUrl"]
    if "fileSize" in version_data:
        version_update.file_size = version_data["fileSize"]
    if "isForceUpdate" in version_data:
        version_update.is_force_update = version_data["isForceUpdate"]
    if "minSupportedVersion" in version_data:
        version_update.min_supported_version = version_data["minSupportedVersion"]
    if "extra" in version_data:
        version_update.extra = version_data["extra"]
    
    updated_version = await version_info.update(db, db_obj=version, obj_in=version_update)
    
    return {
        "id": updated_version.id,
        "versionCode": updated_version.version_code,
        "versionName": updated_version.version_name,
        "platform": updated_version.platform,
        "title": updated_version.title,
        "description": updated_version.description,
        "downloadUrl": updated_version.download_url,
        "fileSize": updated_version.file_size,
        "isForceUpdate": updated_version.is_force_update,
        "minSupportedVersion": updated_version.min_supported_version,
        "extra": updated_version.extra or {},
        "updatedAt": updated_version.updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_version.updated_at else None
    }


@router.delete("/version/{id}")
async def delete_version(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除版本"""
    # 验证版本是否存在
    version = await version_info.get(db, id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    deleted_version = await version_info.remove(db, id=id)
    if not deleted_version:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {}


@router.post("/version/{id}/publish")
async def publish_version(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """发布版本"""
    # 验证版本是否存在
    version = await version_info.get(db, id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    
    # 这里可以添加发布逻辑，比如更新状态、推送给用户等
    # 目前只是返回成功
    return {}

