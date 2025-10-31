from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class PointsResponse(BaseModel):
    """积分记录响应"""
    id: int
    account_id: int
    points: int
    balance: int
    type: str
    description: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    created_at: datetime


class PointsBalanceResponse(BaseModel):
    """积分余额响应"""
    available_balance: int