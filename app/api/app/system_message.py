from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.crud.system_message import get_system_messages
from app.models.system_message import SystemMessageInDB
from app.api.dependencies import get_current_token
from app.db.session import get_db

router = APIRouter()


@router.get("/", response_model=List[SystemMessageInDB])
async def list_system_messages(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    type: Optional[str] = Query(None, description="消息类型 (maintenance/update/announcement/security)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取系统消息列表
    
    - 支持按类型筛选
    - 支持分页
    - 按时间倒序排列
    """
    skip = (page - 1) * page_size
    limit = page_size
    
    messages = await get_system_messages(
        db,
        type=type,
        skip=skip,
        limit=limit
    )
    
    return messages

