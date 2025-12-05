from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.crud.points import (
    get_user_points_balance,
    get_points_history
)
from app.models.points import PointsResponse, PointsBalanceResponse
from app.api.dependencies import get_current_token
from app.db.session import get_db

router = APIRouter()


@router.get("/balance", response_model=PointsBalanceResponse)
async def get_points_balance(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取用户积分余额"""
    account_id = token_info["account_id"]
    balance = await get_user_points_balance(db, account_id)
    return {"available_balance": balance["total_balance"]}


@router.get("/history", response_model=List[PointsResponse])
async def get_points_history_data(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    type: Optional[str] = Query(None, description="积分类型筛选")
):
    """获取积分历史记录"""
    account_id = token_info["account_id"]
    history = await get_points_history(
        db, 
        account_id, 
        skip=skip, 
        limit=limit,
        type=type
    )
    return history
