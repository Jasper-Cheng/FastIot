from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.crud.version_info import version_info
from app.models.version_info import VersionInfo, PlatformEnum

router = APIRouter()


@router.get("/", response_model=List[VersionInfo])
async def get_version_infos(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    order_by: str = Query("created_at"),
    order_desc: bool = Query(True)
):
    """获取版本信息列表
    
    平台信息从token中自动获取，无需传入
    """
    # 从token中获取平台信息
    platform_str = token_info.get("platform", "web")
    
    # 将platform字符串转换为PlatformEnum枚举
    try:
        platform = PlatformEnum(platform_str)
    except ValueError:
        # 如果platform字符串不是有效的PlatformEnum枚举值，抛出异常
        valid_platforms = [p.value for p in PlatformEnum]
        raise HTTPException(
            status_code=400,
            detail=f"Token中的平台标识 '{platform_str}' 无效。有效值: {', '.join(valid_platforms)}"
        )
    
    return await version_info.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        platform=platform,
        order_by=order_by,
        order_desc=order_desc
    )
