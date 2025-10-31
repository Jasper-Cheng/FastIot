from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_db
from app.crud.points import (
    get_user_points_balance,
    get_points_history
)
from app.models.points import PointsResponse, PointsBalanceResponse

router = APIRouter()


@router.get("/balance/{account_id}", response_model=PointsBalanceResponse)
async def get_points_balance(
    account_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取用户积分余额"""
    balance = await get_user_points_balance(db, account_id)
    return {"available_balance": balance["total_balance"]}


@router.get("/history/{account_id}", response_model=List[PointsResponse])
async def get_points_history_data(
    account_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    type: Optional[str] = Query(None, description="积分类型筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取积分历史记录"""
    history = await get_points_history(
        db, 
        account_id, 
        skip=skip, 
        limit=limit,
        type=type
    )
    return history
