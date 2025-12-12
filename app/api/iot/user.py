from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, func, or_, and_
from datetime import datetime, date
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
from app.crud.user_operation_log import user_operation_log
from app.models.account import AccountCreate, AccountUpdate, AccountRole, AccountGender, RegisterRequest, Account
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.db.models.account import Account as DBAccount
from app.db.models.family import Family
from app.db.models.family_member import FamilyMember
from app.db.models.device import Device
from app.core.rsa_crypto import rsa_crypto

router = APIRouter()


@router.get("/user/info")
async def get_user_info(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: DBAccount = Depends(get_current_account),
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


@router.get("/user/today")
async def get_today_new_users(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取今日新增用户列表
    
    返回今日（当天）创建的用户账号（role='user'）
    """
    skip = (page - 1) * pageSize
    
    # 查询今日创建的用户（role='user'）
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    query = select(DBAccount).where(
        and_(
            DBAccount.role == AccountRole.user,
            DBAccount.created_at >= today_start,
            DBAccount.created_at <= today_end
        )
    )
    count_query = select(func.count(DBAccount.id)).where(
        and_(
            DBAccount.role == AccountRole.user,
            DBAccount.created_at >= today_start,
            DBAccount.created_at <= today_end
        )
    )
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据，按创建时间倒序
    result = await db.execute(
        query.order_by(DBAccount.created_at.desc())
        .offset(skip)
        .limit(pageSize)
    )
    accounts = result.scalars().all()
    
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
        "total": total,
        "date": datetime.now().strftime("%Y-%m-%d")
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


@router.post("/user", response_model=Account)
async def create_user(
    req: RegisterRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建用户
    
    必填: phone, password
    可选: nickname, gender, email, avatar
    """
    # 手机号格式校验
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, req.phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确")

    # 手机号唯一性
    phone_exists = await get_account_by_phone(db, req.phone)
    if phone_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号已被使用")

    # 密码必填验证
    if not req.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码不能为空")

    # 规范化并校验邮箱（可选）
    norm_email = (req.email or None)
    if norm_email:
        v = norm_email.strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None
        else:
            norm_email = v
            email_exists = await get_account_by_email(db, norm_email)
            if email_exists:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被使用")

    # 解密密码
    decrypted_password = None
    try:
        decrypted_password = rsa_crypto.decrypt(req.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码解密失败: {str(e)}"
        )
    
    acc = await create_account(
        db,
        AccountCreate(
            password=decrypted_password,
            phone=req.phone,
            nickname=req.nickname,
            gender=req.gender,  # type: ignore[arg-type]
            email=norm_email,
            avatar=req.avatar,
            role=AccountRole.user,  # 固定角色为 user
        ),
    )

    # 记录创建用户操作
    try:
        current_account_id = token_info.get("account_id")
        if current_account_id:
            await user_operation_log.create(
                db=db,
                obj_in=UserOperationLogCreate(
                    operation_type=OperationTypeEnum.register,
                    description=f"创建用户账号（{acc.nickname or acc.phone}）",
                    extra={
                        "registration_type": "user",
                        "phone": acc.phone,
                        "email": acc.email,
                        "created_account_id": acc.id
                    }
                ),
                account_id=current_account_id
            )
    except Exception as e:
        # 记录操作失败不影响创建流程
        print(f"记录创建用户操作失败: {e}")

    return Account.model_validate(acc)


@router.put("/user/{id}")
async def update_user(
    id: int,
    account_update: AccountUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新用户信息
    
    接收一个对象，只更新提供的字段：
    - nickname: 昵称
    - gender: 性别 (male/female/other)
    - email: 邮箱
    - phone: 手机号
    - avatar: 头像URL
    - password: 密码（RSA加密的Base64字符串，会自动解密）
    """
    # 验证用户是否存在
    account = await get_account(db, id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 如果提供了密码，需要先解密
    update_data = account_update.dict(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        try:
            # RSA解密密码
            plain_password = rsa_crypto.decrypt(update_data["password"])
            # 验证密码长度
            if len(plain_password) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密码长度至少6位"
                )
            update_data["password"] = plain_password
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码解密失败: {str(e)}"
            )
    
    # 如果提供了手机号，检查格式和唯一性
    if "phone" in update_data and update_data["phone"]:
        if not validate_phone(update_data["phone"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号格式不正确"
            )
        existing_account = await get_account_by_phone(db, update_data["phone"])
        if existing_account and existing_account.id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已被其他账号使用"
            )
    
    # 如果提供了邮箱，检查格式和唯一性
    if "email" in update_data and update_data["email"]:
        if not validate_email(update_data["email"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱格式不正确"
            )
        existing_email = await get_account_by_email(db, update_data["email"])
        if existing_email and existing_email.id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被其他账号使用"
            )
    
    # 创建更新对象
    update_obj = AccountUpdate(**update_data)
    
    # 更新账号信息
    updated_account = await update_account(db, id, update_obj)
    
    if not updated_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    # 记录操作日志
    try:
        current_account_id = token_info.get("account_id")
        if current_account_id:
            await user_operation_log.create(
                db=db,
                obj_in=UserOperationLogCreate(
                    operation_type=OperationTypeEnum.account_update,
                    description=f"更新用户信息 (ID: {id})",
                    extra={"updated_fields": list(update_data.keys()), "target_user_id": id}
                ),
                account_id=current_account_id
            )
    except Exception as e:
        # 记录操作失败不影响更新流程
        print(f"记录操作日志失败: {e}")
    
    return {
        "id": updated_account.id,
        "nickname": updated_account.nickname,
        "phone": updated_account.phone,
        "email": updated_account.email,
        "avatar": updated_account.avatar,
        "gender": updated_account.gender,
        "role": updated_account.role,
        "createdAt": updated_account.created_at.strftime("%Y-%m-%d %H:%M:%S") if updated_account.created_at else None
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

