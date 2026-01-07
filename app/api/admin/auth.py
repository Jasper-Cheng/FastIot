from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import re

from app.db.session import get_db
from app.api.dependencies import get_current_token, get_current_account
from app.api.utils import log_operation_with_token
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.account import (
    get_account,
    get_account_by_phone,
    get_account_by_email,
    create_account,
    delete_account
)
from app.models.account import (
    LoginRequest,
    TokenResponse,
    Account,
    AccountRole,
    AccountGender,
    AccountCreate
)
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


@router.get("/auth/rsa_public_key")
async def get_rsa_public_key():
    """获取RSA公钥接口
    
    前端需要先调用此接口获取公钥，然后使用公钥加密密码。
    返回公钥（PEM格式），前端可以使用此公钥加密密码。
    """
    try:
        public_key = rsa_crypto.get_public_key()
        return {
            "public_key": public_key,
            "format": "PEM"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取公钥失败: {str(e)}"
        )


@router.post("/auth/login", response_model=dict)
async def admin_login(
    db: AsyncSession = Depends(get_db),
    payload: LoginRequest = Body(...)
):
    """管理员登录接口
    
    说明：
    - phone 为手机号
    - password 为加密后的密码（RSA加密）
    - 只允许 role='admin' 的账号登录
    """
    # 验证手机号格式
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, payload.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号格式不正确"
        )
    
    # 按手机号查找账号
    acc = await get_account_by_phone(db, payload.phone)
    
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    
    # 验证是否为管理员
    if acc.role != AccountRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账号不是管理员，无权访问后台管理系统"
        )
    
    # 验证密码
    if not payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码不能为空"
        )
    
    # 解密密码
    try:
        plain_password = rsa_crypto.decrypt(payload.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码解密失败: {str(e)}"
        )
    
    # 验证密码
    if not acc.password or not verify_password(plain_password, acc.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    
    # 生成 JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "account_id": acc.id,
        "role": acc.role,
        "platform": "web",  # 后台管理系统使用 web 平台
    }
    
    token = create_access_token(
        expires_delta=access_token_expires,
        extra_claims=extra_claims
    )
    
    # 记录登录操作
    token_info_for_log = {"account_id": acc.id, "platform": "web"}
    await log_operation_with_token(
        db=db,
        token_info=token_info_for_log,
        operation_type=OperationTypeEnum.login,
        description=f"管理员登录系统（{acc.nickname or acc.phone}）",
        extra={
            "login_type": "admin",
            "platform": "web",
            "phone": acc.phone
        }
    )
    
    # 返回 accessToken（按照文档要求，直接返回 accessToken 字符串）
    return {
        "accessToken": token
    }


@router.post("/auth/register", response_model=dict)
async def admin_register(
    db: AsyncSession = Depends(get_db),
    register_data: dict = Body(...)
):
    """管理员注册接口
    
    说明：
    - phone 为手机号（必填）
    - password 为加密后的密码（RSA加密，必填）
    - nickname 为昵称（必填）
    - email 为邮箱（可选，需要验证格式）
    - avatar 为头像（可选，Base64字符串）
    - gender 为性别（可选：'male' | 'female' | 'other'）
    - 创建的角色固定为 admin
    """
    # 验证必填字段
    if not register_data.get("nickname"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="昵称不能为空"
        )
    if not register_data.get("phone"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号不能为空"
        )
    if not register_data.get("password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码不能为空"
        )
    
    # 验证手机号格式
    if not validate_phone(register_data["phone"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号格式不正确"
        )
    
    # 验证手机号唯一性
    existing_account = await get_account_by_phone(db, register_data["phone"])
    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已被使用"
        )
    
    # 验证邮箱格式（如果提供）
    norm_email = None
    if register_data.get("email"):
        email_value = register_data["email"].strip().lower()
        if email_value and email_value not in ("", "string", "null", "undefined"):
            if not validate_email(email_value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱格式不正确"
                )
            # 验证邮箱唯一性
            existing_email = await get_account_by_email(db, email_value)
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被使用"
                )
            norm_email = email_value
    
    # 解密密码
    decrypted_password = None
    try:
        decrypted_password = rsa_crypto.decrypt(register_data["password"])
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码解密失败: {str(e)}"
        )
    
    # 创建管理员账号
    account_create = AccountCreate(
        nickname=register_data["nickname"],
        phone=register_data["phone"],
        email=norm_email,
        password=decrypted_password,
        avatar=register_data.get("avatar"),
        gender=AccountGender(register_data["gender"]) if register_data.get("gender") else None,
        role=AccountRole.admin  # 固定角色为 admin
    )
    
    account = await create_account(db, account_create)
    
    # 记录注册操作
    token_info_for_log = {"account_id": account.id, "platform": "web"}
    await log_operation_with_token(
        db=db,
        token_info=token_info_for_log,
        operation_type=OperationTypeEnum.register,
        description=f"管理员注册新账号（{account.nickname or account.phone}）",
        extra={
            "registration_type": "admin",
            "phone": account.phone,
            "email": account.email
        }
    )
    
    # 返回创建的账号信息
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


@router.delete("/auth/account/{id}")
async def delete_admin_account(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account)
):
    """删除管理员账户接口
    
    说明：
    - 需要管理员权限
    - 不能删除自己
    - 验证要删除的账户是管理员
    - 记录删除操作日志
    """
    # 验证当前用户是否为管理员
    if current_account.role != AccountRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权执行此操作，需要管理员权限"
        )
    
    # 不能删除自己
    if current_account.id == id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户"
        )
    
    # 验证要删除的管理员是否存在
    account_to_delete = await get_account(db, id)
    if not account_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在"
        )
    
    # 验证要删除的账户是否为管理员
    if account_to_delete.role != AccountRole.admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账户不是管理员，无法删除"
        )
    
    # 记录删除前的信息（用于日志）
    deleted_account_info = {
        "id": account_to_delete.id,
        "nickname": account_to_delete.nickname,
        "phone": account_to_delete.phone,
        "email": account_to_delete.email
    }
    
    # 执行删除
    success = await delete_account(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除失败"
        )
    
    # 记录删除操作
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.account_delete,
        description=f"管理员 {current_account.nickname or current_account.phone} 删除了管理员账户（{account_to_delete.nickname or account_to_delete.phone}）",
        extra={
            "deleted_account": deleted_account_info,
            "operator": {
                "id": current_account.id,
                "nickname": current_account.nickname,
                "phone": current_account.phone
            }
        }
    )
    
    return {}

