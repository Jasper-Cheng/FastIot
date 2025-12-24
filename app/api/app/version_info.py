from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.version_info import version_info as version_info_crud
from app.models.version_info import VersionInfo as VersionInfoResponse, PlatformEnum
from app.db.session import get_db

router = APIRouter()


@router.get("/", response_model=VersionInfoResponse)
async def get_version_info(
    db: AsyncSession = Depends(get_db)
):
    """获取最新版本信息（App端）
    
    - 不需要认证，任何用户都可以访问
    - 返回App平台的最新版本信息，用于检查更新
    """
    # 获取App平台的最新版本
    latest_version = await version_info_crud.get_latest_by_platform(db, platform=PlatformEnum.app)
    
    if not latest_version:
        # 如果没有版本信息，返回404
        raise HTTPException(status_code=404, detail="暂无版本信息")
    
    return VersionInfoResponse.model_validate(latest_version)

