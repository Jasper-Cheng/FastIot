from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_db
from app.crud.version_info import version_info
from app.models.version_info import VersionInfo

router = APIRouter()


@router.get("/", response_model=List[VersionInfo])
async def get_version_infos(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    platform: Optional[str] = Query(None),
    order_by: str = Query("created_at"),
    order_desc: bool = Query(True)
):
    """获取版本信息列表"""
    return await version_info.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        platform=platform,
        order_by=order_by,
        order_desc=order_desc
    )
