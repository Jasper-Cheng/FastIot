from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import re

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.api.utils import extract_token_info, log_operation_with_token
from app.crud.account import (
    get_account,
    get_account_by_phone,
    get_account_by_email,
    create_account,
    update_account,
    delete_account,
    get_accounts_with_pagination
)
from app.models.account import AccountCreate, AccountUpdate, AccountRole, AccountGender, RegisterRequest, Account
from app.models.user_operation_log import OperationTypeEnum
from app.core.rsa_crypto import rsa_crypto

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


@router.post("/account", response_model=Account)
async def create_admin_account(
    req: RegisterRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建管理员
    
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
            role=AccountRole.admin,  # 固定角色为 admin
        ),
    )

    # 记录创建管理员操作
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.register,
        description=f"创建管理员账号（{acc.nickname or acc.phone}）",
        extra={
            "registration_type": "admin",
            "phone": acc.phone,
            "email": acc.email,
            "created_account_id": acc.id
        }
    )

    return Account.model_validate(acc)


@router.put("/account/{id}")
async def update_admin_account(
    id: int,
    account_update: AccountUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新管理员信息
    
    接收一个对象，只更新提供的字段：
    - nickname: 昵称
    - gender: 性别 (male/female/other)
    - email: 邮箱
    - phone: 手机号
    - avatar: 头像URL
    - password: 密码（RSA加密的Base64字符串，会自动解密）
    """
    # 验证管理员是否存在
    account = await get_account(db, id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="管理员不存在")
    
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
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.account_update,
        description=f"更新管理员信息 (ID: {id})",
        extra={"updated_fields": list(update_data.keys()), "target_account_id": id}
    )
    
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
    
    # 保存账号信息用于日志
    account_name = account.nickname or account.phone
    account_phone = account.phone
    
    success = await delete_account(db, id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.account_delete,
        description=f"删除管理员账号：{account_name}（{account_phone}）",
        extra={
            "deleted_account_id": id,
            "deleted_account_name": account_name,
            "deleted_account_phone": account_phone,
            "deleted_account_role": account.role
        }
    )
    
    return {}

