from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.version_info import version_info as version_info_crud
from app.models.version_info import VersionInfo as VersionInfoResponse, PlatformEnum
from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.api.utils import extract_token_info

router = APIRouter()

"""
版本信息模块 - Client API

【App + Web 通用】
所有接口支持 App 和 Web 平台，根据 token.platform 字段自动返回对应平台的版本信息。
"""


@router.get("/", response_model=VersionInfoResponse)
async def get_version_info(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取最新版本信息
    
    - 需要 token 认证
    - 根据 token 中的平台信息自动返回对应平台的最新版本信息，用于检查更新
    """
    # 从token中获取平台信息
    _, platform_str, _ = extract_token_info(token_info)
    
    # 将platform字符串转换为PlatformEnum枚举
    try:
        platform = PlatformEnum(platform_str)
    except ValueError:
        # 如果platform字符串不是有效的PlatformEnum枚举值，抛出异常
        valid_platforms = [p.value for p in PlatformEnum]
        raise HTTPException(status_code=400, detail=f"Token中的平台标识 '{platform_str}' 无效。有效值: {', '.join(valid_platforms)}")
    
    # 获取指定平台的最新版本
    latest_version = await version_info_crud.get_latest_by_platform(db, platform=platform)
    
    if not latest_version:
        # 如果没有版本信息，返回404
        raise HTTPException(status_code=404, detail="暂无版本信息")
    
    return VersionInfoResponse.model_validate(latest_version)

