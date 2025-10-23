from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_db, get_current_account, get_current_admin
from app.crud.user_operation_log import user_operation_log
from app.models.user_operation_log import UserOperationLog, UserOperationLogCreate, UserOperationLogUpdate
from app.db.models.account import Account
from app.db.models.admin import Admin

router = APIRouter()

@router.post("/", response_model=UserOperationLog)
async def create_operation_log(
    *,
    db: AsyncSession = Depends(get_db),
    operation_log_in: UserOperationLogCreate,
    current_account: Account = Depends(get_current_account)
):
    """创建用户操作记录"""
    return await user_operation_log.create(db=db, obj_in=operation_log_in, account_id=current_account.id)

@router.get("/", response_model=List[UserOperationLog])
async def get_operation_logs(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    account_id: Optional[int] = Query(None),
    operation_type: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    order_by: str = Query("created_at"),
    order_desc: bool = Query(True),
    current_account: Account = Depends(get_current_account)
):
    """获取操作记录列表"""
    # 根据用户角色决定返回的数据
    if current_account.role == "admin":
        # 管理员可以看到所有操作记录
        return await user_operation_log.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            account_id=account_id,
            operation_type=operation_type,
            result=result,
            order_by=order_by,
            order_desc=order_desc
        )
    else:
        # 普通用户只能看到自己的操作记录
        return await user_operation_log.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            account_id=current_account.id,
            operation_type=operation_type,
            result=result,
            order_by=order_by,
            order_desc=order_desc
        )

@router.get("/my", response_model=List[UserOperationLog])
async def get_my_operation_logs(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_account: Account = Depends(get_current_account)
):
    """获取当前用户的操作记录"""
    return await user_operation_log.get_by_account(
        db=db,
        account_id=current_account.id,
        skip=skip,
        limit=limit
    )

@router.get("/recent", response_model=List[UserOperationLog])
async def get_recent_operations(
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168, description="最近N小时"),
    limit: int = Query(50, ge=1, le=200),
    current_account: Account = Depends(get_current_account)
):
    """获取最近N小时的操作记录"""
    return await user_operation_log.get_recent_operations(
        db=db,
        account_id=current_account.id,
        hours=hours,
        limit=limit
    )

@router.get("/failed", response_model=List[UserOperationLog])
async def get_failed_operations(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_admin: Admin = Depends(get_current_admin)
):
    """获取失败的操作记录（管理员）"""
    return await user_operation_log.get_failed_operations(db=db, skip=skip, limit=limit)

@router.get("/statistics")
async def get_operation_statistics(
    db: AsyncSession = Depends(get_db),
    account_id: Optional[int] = Query(None),
    current_admin: Admin = Depends(get_current_admin)
):
    """获取操作统计信息（管理员）"""
    return await user_operation_log.get_statistics(db=db, account_id=account_id)

@router.get("/{operation_log_id}", response_model=UserOperationLog)
async def get_operation_log(
    *,
    db: AsyncSession = Depends(get_db),
    operation_log_id: int,
    current_account: Account = Depends(get_current_account)
):
    """根据ID获取操作记录"""
    operation_log_obj = await user_operation_log.get(db=db, id=operation_log_id)
    if not operation_log_obj:
        raise HTTPException(
            status_code=404,
            detail="操作记录不存在"
        )

    # 只有记录创建者或管理员可以查看
    if operation_log_obj.account_id != current_account.id and current_account.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="无权限查看此操作记录"
        )

    return operation_log_obj

@router.put("/{operation_log_id}", response_model=UserOperationLog)
async def update_operation_log(
    *,
    db: AsyncSession = Depends(get_db),
    operation_log_id: int,
    operation_log_in: UserOperationLogUpdate,
    current_admin: Admin = Depends(get_current_admin)
):
    """更新操作记录（管理员）"""
    operation_log_obj = await user_operation_log.get(db=db, id=operation_log_id)
    if not operation_log_obj:
        raise HTTPException(
            status_code=404,
            detail="操作记录不存在"
        )

    return await user_operation_log.update(db=db, db_obj=operation_log_obj, obj_in=operation_log_in)

@router.delete("/{operation_log_id}")
async def delete_operation_log(
    *,
    db: AsyncSession = Depends(get_db),
    operation_log_id: int,
    current_admin: Admin = Depends(get_current_admin)
):
    """删除操作记录（管理员）"""
    operation_log_obj = await user_operation_log.get(db=db, id=operation_log_id)
    if not operation_log_obj:
        raise HTTPException(
            status_code=404,
            detail="操作记录不存在"
        )

    await user_operation_log.remove(db=db, id=operation_log_id)
    return {"message": "操作记录已删除"}

@router.get("/search/{keyword}")
async def search_operation_logs(
    *,
    db: AsyncSession = Depends(get_db),
    keyword: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_admin: Admin = Depends(get_current_admin)
):
    """搜索操作记录（管理员）"""
    return await user_operation_log.search(db=db, keyword=keyword, skip=skip, limit=limit)
