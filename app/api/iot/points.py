from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.points import (
    get_latest_points_by_all_accounts,
    get_latest_points_by_all_accounts_count,
    get_user_latest_points,
    get_points_history,
    add_points,
    deduct_points,
    get_user_points_balance
)
from app.models.points import PointsResponse
from app.crud.account import get_account
from app.db.models.account import Account as DBAccount

router = APIRouter()


@router.get("/points/list", response_model=Dict[str, Any])
async def get_all_users_latest_points(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    accountId: Optional[int] = Query(None, description="账号ID筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取所有用户的最新一条积分记录"""
    skip = (page - 1) * pageSize
    
    # 如果指定了 accountId，直接查询该用户的最新记录
    if accountId is not None:
        latest = await get_user_latest_points(db, accountId)
        points_records = [latest] if latest else []
        total = 1 if latest else 0
    else:
        # 获取所有用户的最新积分记录
        points_records = await get_latest_points_by_all_accounts(db, skip=skip, limit=pageSize)
        total = await get_latest_points_by_all_accounts_count(db)
    
    items = []
    for point in points_records:
        # 获取账号信息
        account = await get_account(db, point.account_id)
        account_name = account.nickname if account else None
        account_phone = account.phone if account else None
        
        items.append({
            "id": point.id,
            "accountId": point.account_id,
            "accountName": account_name,
            "accountPhone": account_phone,
            "points": point.points,
            "balance": point.balance,
            "type": point.type,
            "description": point.description,
            "extra": point.extra,
            "createdAt": point.created_at.strftime("%Y-%m-%d %H:%M:%S") if point.created_at else None
        })
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize
    }


@router.get("/points/{accountId}/detail", response_model=Dict[str, Any])
async def get_user_points_detail(
    accountId: int,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(20, ge=1, le=100, description="每页数量"),
    type: Optional[str] = Query(None, description="积分类型筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """查看积分详情：获取某个用户的所有积分记录"""
    # 验证账号是否存在
    account = await get_account(db, accountId)
    if not account:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    skip = (page - 1) * pageSize
    
    # 获取积分历史记录
    points_records = await get_points_history(
        db,
        account_id=accountId,
        skip=skip,
        limit=pageSize,
        type=type
    )
    
    # 获取总记录数（需要单独查询）
    from sqlalchemy import select, func
    from app.db.models.points import Points
    
    count_query = select(func.count(Points.id)).where(Points.account_id == accountId)
    if type:
        count_query = count_query.where(Points.type == type)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # 获取当前积分余额
    balance_info = await get_user_points_balance(db, accountId)
    
    items = []
    for point in points_records:
        items.append({
            "id": point.id,
            "points": point.points,
            "balance": point.balance,
            "type": point.type,
            "description": point.description,
            "extra": point.extra,
            "createdAt": point.created_at.strftime("%Y-%m-%d %H:%M:%S") if point.created_at else None
        })
    
    return {
        "accountId": accountId,
        "accountName": account.nickname,
        "accountPhone": account.phone,
        "currentBalance": balance_info["total_balance"],
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize
    }


@router.post("/points/{accountId}/adjust", response_model=Dict[str, Any])
async def adjust_user_points(
    accountId: int,
    points_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """积分奖励/积分扣除：在某个用户最新的积分记录上添加一条新的积分记录"""
    # 验证账号是否存在
    account = await get_account(db, accountId)
    if not account:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 获取参数
    points = points_data.get("points")
    points_type = points_data.get("type", "admin_adjust")
    description = points_data.get("description", "")
    extra = points_data.get("extra")
    
    # 验证必填参数
    if points is None:
        raise HTTPException(status_code=400, detail="积分变动数量不能为空")
    
    if not isinstance(points, int):
        raise HTTPException(status_code=400, detail="积分变动数量必须是整数")
    
    # 验证积分类型
    valid_types = ['check_in', 'task', 'reward', 'exchange', 'penalty', 'admin_adjust']
    if points_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"积分类型必须是以下之一: {', '.join(valid_types)}")
    
    # 获取当前积分余额
    balance_info = await get_user_points_balance(db, accountId)
    current_balance = balance_info["total_balance"]
    
    # 计算新的余额
    new_balance = current_balance + points
    
    # 如果扣除后余额为负数，不允许操作
    if new_balance < 0:
        raise HTTPException(
            status_code=400,
            detail=f"积分扣除后余额不能为负数。当前余额: {current_balance}，尝试扣除: {abs(points)}"
        )
    
    # 构建积分记录数据
    points_record_data = {
        "account_id": accountId,
        "points": points,
        "balance": new_balance,
        "type": points_type,
        "description": description or (f"管理员{'奖励' if points > 0 else '扣除'}积分" if not description else description),
        "extra": extra or {
            "operator": token_info.get("account_id"),
            "operator_role": token_info.get("role"),
            "operation": "admin_adjust"
        }
    }
    
    # 添加积分记录
    if points > 0:
        new_point = await add_points(db, points_record_data)
    else:
        new_point = await deduct_points(db, points_record_data)
    
    # 记录操作日志
    try:
        from app.crud.user_operation_log import user_operation_log
        from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
        
        operation_type = OperationTypeEnum.points_adjust if points > 0 else OperationTypeEnum.points_deduct
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=operation_type,
                description=f"{'奖励' if points > 0 else '扣除'}用户 {account.nickname or account.phone} {abs(points)} 积分",
                extra={
                    "account_id": accountId,
                    "account_name": account.nickname,
                    "account_phone": account.phone,
                    "points": points,
                    "old_balance": current_balance,
                    "new_balance": new_balance,
                    "type": points_type,
                    "description": description
                }
            ),
            account_id=token_info.get("account_id")
        )
    except Exception as e:
        # 记录操作失败不影响积分调整流程
        print(f"记录积分调整操作日志失败: {e}")
    
    return {
        "id": new_point.id,
        "accountId": accountId,
        "accountName": account.nickname,
        "accountPhone": account.phone,
        "points": new_point.points,
        "oldBalance": current_balance,
        "newBalance": new_point.balance,
        "type": new_point.type,
        "description": new_point.description,
        "extra": new_point.extra,
        "createdAt": new_point.created_at.strftime("%Y-%m-%d %H:%M:%S") if new_point.created_at else None
    }

