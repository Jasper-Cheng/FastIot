from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
import re

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.account import (
    get_account,
    get_account_by_phone,
    get_account_by_email,
    create_account,
    update_account,
    delete_account,
    get_accounts_with_pagination
)
from app.models.account import AccountCreate, AccountUpdate, AccountRole, AccountGender
from app.db.models.account import Account

router = APIRouter()


def validate_phone(phone: str) -> bool:
    """验证手机号格式"""
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


@router.get("/account/list")
async def get_account_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    nickname: Optional[str] = Query(None, description="昵称搜索（模糊匹配）"),
    phone: Optional[str] = Query(None, description="手机号搜索（模糊匹配）"),
    email: Optional[str] = Query(None, description="邮箱搜索（模糊匹配）"),
    role: Optional[AccountRole] = Query(None, description="角色筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取管理员列表（支持分页和搜索）"""
    skip = (page - 1) * pageSize
    
    accounts, total = await get_accounts_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        nickname=nickname,
        phone=phone,
        email=email,
        role=role.value if role else None
    )
    
    items = []
    for account in accounts:
        items.append({
            "id": account.id,
            "nickname": account.nickname,
            "phone": account.phone,
            "email": account.email,
            "password": account.password,  # 返回密码字段（前端需要直接显示）
            "avatar": account.avatar,
            "gender": account.gender,
            "role": account.role,
            "currentFamilyId": account.current_family_id,
            "createdAt": account.created_at.strftime("%Y-%m-%d %H:%M:%S") if account.created_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.post("/account")
async def create_admin_account(
    account_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建管理员"""
    # 验证必填字段
    if not account_data.get("nickname"):
        raise HTTPException(status_code=400, detail="昵称不能为空")
    if not account_data.get("phone"):
        raise HTTPException(status_code=400, detail="手机号不能为空")
    if not account_data.get("password"):
        raise HTTPException(status_code=400, detail="密码不能为空")
    
    # 验证手机号格式
    if not validate_phone(account_data["phone"]):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    
    # 验证手机号唯一性
    existing_account = await get_account_by_phone(db, account_data["phone"])
    if existing_account:
        raise HTTPException(status_code=400, detail="手机号已存在")
    
    # 验证邮箱格式（如果提供）
    if account_data.get("email"):
        if not validate_email(account_data["email"]):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        # 验证邮箱唯一性
        existing_email = await get_account_by_email(db, account_data["email"])
        if existing_email:
            raise HTTPException(status_code=400, detail="邮箱已存在")
    
    # 创建账号
    account_create = AccountCreate(
        nickname=account_data["nickname"],
        phone=account_data["phone"],
        email=account_data.get("email"),
        password=account_data["password"],
        avatar=account_data.get("avatar"),
        gender=AccountGender(account_data["gender"]) if account_data.get("gender") else None,
        role=AccountRole.admin  # 默认角色为 admin
    )
    
    account = await create_account(db, account_create)
    
    return {
        "id": account.id,
        "nickname": account.nickname,
        "phone": account.phone,
        "email": account.email,
        "avatar": account.avatar,
        "gender": account.gender,
        "role": account.role,
        "createdAt": account.created_at.strftime("%Y-%m-%d %H:%M:%S") if account.created_at else None
    }


@router.put("/account/{id}")
async def update_admin_account(
    id: int,
    account_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新管理员信息"""
    # 验证管理员是否存在
    account = await get_account(db, id)
    if not account:
        raise HTTPException(status_code=404, detail="管理员不存在")
    
    # 验证手机号格式（如果提供）
    if account_data.get("phone"):
        if not validate_phone(account_data["phone"]):
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        # 验证手机号唯一性（排除自己）
        existing_account = await get_account_by_phone(db, account_data["phone"])
        if existing_account and existing_account.id != id:
            raise HTTPException(status_code=400, detail="手机号已存在")
    
    # 验证邮箱格式（如果提供）
    if account_data.get("email"):
        if not validate_email(account_data["email"]):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        # 验证邮箱唯一性（排除自己）
        existing_email = await get_account_by_email(db, account_data["email"])
        if existing_email and existing_email.id != id:
            raise HTTPException(status_code=400, detail="邮箱已存在")
    
    # 构建更新数据
    update_data = AccountUpdate()
    if "nickname" in account_data:
        update_data.nickname = account_data["nickname"]
    if "phone" in account_data:
        update_data.phone = account_data["phone"]
    if "email" in account_data:
        update_data.email = account_data["email"]
    if "avatar" in account_data:
        update_data.avatar = account_data["avatar"]
    if "gender" in account_data:
        update_data.gender = AccountGender(account_data["gender"])
    if "role" in account_data:
        update_data.role = AccountRole(account_data["role"])
    
    updated_account = await update_account(db, id, update_data)
    if not updated_account:
        raise HTTPException(status_code=500, detail="更新失败")
    
    return {
        "id": updated_account.id,
        "nickname": updated_account.nickname,
        "phone": updated_account.phone,
        "email": updated_account.email,
        "avatar": updated_account.avatar,
        "gender": updated_account.gender,
        "role": updated_account.role,
        "updatedAt": updated_account.updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_account.updated_at else None
    }


@router.delete("/account/{id}")
async def delete_admin_account(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除管理员"""
    # 验证管理员是否存在
    account = await get_account(db, id)
    if not account:
        raise HTTPException(status_code=404, detail="管理员不存在")
    
    success = await delete_account(db, id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {}

