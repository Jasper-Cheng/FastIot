from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.version_info import get_latest_version_info
from app.models.version_info import VersionInfoInDB
from app.db.session import get_db

router = APIRouter()


@router.get("/", response_model=VersionInfoInDB)
async def get_version_info(
    db: AsyncSession = Depends(get_db)
):
    """获取最新版本信息
    
    - 不需要认证，任何用户都可以访问
    - 返回最新的版本信息，用于检查更新
    """
    version_info = await get_latest_version_info(db)
    if not version_info:
        # 如果没有版本信息，返回默认值
        return VersionInfoInDB(
            id=0,
            version="1.0.0",
            build_number=1,
            update_time="2025-01-01",
            description="首次发布版本",
            download_url="",
            force_update=False,
            created_at=None,
            updated_at=None
        )
    
    return VersionInfoInDB.model_validate(version_info)

