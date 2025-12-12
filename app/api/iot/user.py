from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, func, or_
import re

from app.db.session import get_db
from app.api.dependencies import get_current_token, get_current_account
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
from app.db.models.family import Family
from app.db.models.family_member import FamilyMember
from app.db.models.device import Device

router = APIRouter()


@router.get("/user/info")
async def get_user_info(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account),
):
    """获取当前管理员个人信息"""
    # 验证是否为管理员
    if current_account.role != AccountRole.admin:
        raise HTTPException(status_code=403, detail="该账号不是管理员，无权访问")
    
    return {
        "id": current_account.id,
        "nickname": current_account.nickname,
        "phone": current_account.phone,
        "email": current_account.email,
        "avatar": current_account.avatar,
        "gender": current_account.gender,
        "role": current_account.role,
        "createdAt": current_account.created_at.strftime("%Y-%m-%d %H:%M:%S") if current_account.created_at else None
    }


def validate_phone(phone: str) -> bool:
    """验证手机号格式"""
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


@router.get("/user/list")
async def get_user_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    nickname: Optional[str] = Query(None, description="昵称搜索（模糊匹配）"),
    phone: Optional[str] = Query(None, description="手机号搜索（模糊匹配）"),
    email: Optional[str] = Query(None, description="邮箱搜索（模糊匹配）"),
    gender: Optional[str] = Query(None, description="性别筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取 App 用户列表"""
    skip = (page - 1) * pageSize
    
    # 只查询 role='user' 的用户
    accounts, total = await get_accounts_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        nickname=nickname,
        phone=phone,
        email=email,
        role='user'  # 只查询用户角色
    )
    
    # 如果提供了性别筛选，需要额外过滤
    if gender:
        accounts = [acc for acc in accounts if acc.gender == gender]
        total = len(accounts)
    
    items = []
    for account in accounts:
        # 获取当前家庭名称
        current_family_name = None
        if account.current_family_id:
            family_result = await db.execute(
                select(Family).filter(Family.id == account.current_family_id)
            )
            family = family_result.scalar_one_or_none()
            if family:
                current_family_name = family.name
        
        # 统计设备数
        device_count_result = await db.execute(
            select(func.count(Device.id)).filter(Device.account_id == account.id)
        )
        device_count = device_count_result.scalar() or 0
        
        # 统计家庭数
        family_count_result = await db.execute(
            select(func.count(FamilyMember.id)).filter(FamilyMember.account_id == account.id)
        )
        family_count = family_count_result.scalar() or 0
        
        items.append({
            "id": account.id,
            "nickname": account.nickname,
            "phone": account.phone,
            "email": account.email,
            "avatar": account.avatar,
            "password": account.password,  # 前端需要显示密码
            "unionid": account.unionid,
            "gender": account.gender,
            "role": account.role,
            "currentFamilyId": account.current_family_id,
            "currentFamilyName": current_family_name,
            "deviceCount": device_count,
            "familyCount": family_count,
            "createdAt": account.created_at.strftime("%Y-%m-%d %H:%M:%S") if account.created_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.post("/user")
async def create_user(
    user_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建用户"""
    # 验证必填字段
    if not user_data.get("nickname"):
        raise HTTPException(status_code=400, detail="昵称不能为空")
    if not user_data.get("phone"):
        raise HTTPException(status_code=400, detail="手机号不能为空")
    if not user_data.get("password"):
        raise HTTPException(status_code=400, detail="密码不能为空")
    
    # 验证手机号格式
    if not validate_phone(user_data["phone"]):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    
    # 验证手机号唯一性
    existing_account = await get_account_by_phone(db, user_data["phone"])
    if existing_account:
        raise HTTPException(status_code=400, detail="手机号已存在")
    
    # 验证邮箱格式（如果提供）
    if user_data.get("email"):
        if not validate_email(user_data["email"]):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        # 验证邮箱唯一性
        existing_email = await get_account_by_email(db, user_data["email"])
        if existing_email:
            raise HTTPException(status_code=400, detail="邮箱已存在")
    
    # 创建账号
    account_create = AccountCreate(
        nickname=user_data["nickname"],
        phone=user_data["phone"],
        email=user_data.get("email"),
        password=user_data["password"],
        avatar=user_data.get("avatar"),
        gender=AccountGender(user_data["gender"]) if user_data.get("gender") else None,
        role=AccountRole.user  # 默认角色为 user
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


@router.put("/user/{id}")
async def update_user(
    id: int,
    user_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新用户信息"""
    # 验证用户是否存在
    account = await get_account(db, id)
    if not account:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 验证手机号格式（如果提供）
    if user_data.get("phone"):
        if not validate_phone(user_data["phone"]):
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        # 验证手机号唯一性（排除自己）
        existing_account = await get_account_by_phone(db, user_data["phone"])
        if existing_account and existing_account.id != id:
            raise HTTPException(status_code=400, detail="手机号已存在")
    
    # 验证邮箱格式（如果提供）
    if user_data.get("email"):
        if not validate_email(user_data["email"]):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        # 验证邮箱唯一性（排除自己）
        existing_email = await get_account_by_email(db, user_data["email"])
        if existing_email and existing_email.id != id:
            raise HTTPException(status_code=400, detail="邮箱已存在")
    
    # 构建更新数据
    update_data = AccountUpdate()
    if "nickname" in user_data:
        update_data.nickname = user_data["nickname"]
    if "phone" in user_data:
        update_data.phone = user_data["phone"]
    if "email" in user_data:
        update_data.email = user_data["email"]
    if "avatar" in user_data:
        update_data.avatar = user_data["avatar"]
    if "gender" in user_data:
        update_data.gender = AccountGender(user_data["gender"])
    if "role" in user_data:
        update_data.role = AccountRole(user_data["role"])
    
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
        "role": updated_account.role
    }


@router.delete("/user/{id}")
async def delete_user(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除用户"""
    # 验证用户是否存在
    account = await get_account(db, id)
    if not account:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    success = await delete_account(db, id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {}

