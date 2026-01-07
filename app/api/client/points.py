from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.crud.points import get_user_points_balance, get_points_history
from app.models.points import PointsResponse
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.api.utils import extract_token_info

router = APIRouter()

"""
积分功能模块 - Client API

【App + Web 通用】
所有接口支持 App 和 Web 平台，平台信息通过 token.platform 字段识别。
"""


@router.get("/balance")
async def get_balance(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取当前用户的积分余额"""
    account_id, _, _ = extract_token_info(token_info)
    balance_info = await get_user_points_balance(db, account_id)
    balance = balance_info.get("total_balance", 0)
    return {"balance": balance}


@router.get("/history", response_model=List[PointsResponse])
async def list_points_history(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取当前用户的积分历史记录
    
    - 包含所有获取、消耗、过期的积分记录
    - 按时间倒序排列
    - 支持分页
    """
    account_id, _, _ = extract_token_info(token_info)
    skip = (page - 1) * page_size
    limit = page_size
    
    history = await get_points_history(db, account_id, skip=skip, limit=limit)
    return history

