from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Literal
from pydantic import BaseModel, constr
import re

from app.db.session import get_db
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.account import (
    get_account_by_account_name,
    get_account_by_phone,
    get_account_by_email,
    create_account,
)
from app.crud.user import create_user, get_user_by_account_id
from app.crud.member import create_member, get_member_by_account_id
from app.models.account import AccountCreate, AccountLogin, Account, AccountRole, AccountGender

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    role: AccountRole
    account: Account

class LoginRequest(BaseModel):
    account: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """统一登录：使用 account 字段 + password。

    说明：
    - account 可传登录名或手机号
    - 验证顺序：先按登录名查询，未命中再按手机号查询
    """
    # 先按账号查找，未找到则按手机号查找
    acc = await get_account_by_account_name(db, payload.account)
    if not acc:
        acc = await get_account_by_phone(db, payload.account)

    if not acc or not verify_password(payload.password, acc.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "user_type": "account",
        "account_id": acc.id,
        "account": acc.account,
        "role": acc.role,
    }
    # 附带 user_id/member_id 便于后续权限判断
    user = await get_user_by_account_id(db, acc.id)
    if user:
        extra_claims["user_id"] = user.id
    member = await get_member_by_account_id(db, acc.id)
    if member:
        extra_claims["member_id"] = member.id

    token = create_access_token(expires_delta=access_token_expires, extra_claims=extra_claims)

    return TokenResponse(access_token=token, role=acc.role, account=Account.model_validate(acc))


@router.post("/login/form", response_model=TokenResponse, include_in_schema=False)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """表单登录：兼容 Swagger Authorize（OAuth2 Password flow）

    - username 支持传登录名或手机号
    - password 为明文密码
    - 忽略 scope 和 client 相关字段
    """
    # 先按账号查找，未找到则按手机号查找
    acc = await get_account_by_account_name(db, form_data.username)
    if not acc:
        acc = await get_account_by_phone(db, form_data.username)

    if not acc or not verify_password(form_data.password, acc.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "user_type": "account",
        "account_id": acc.id,
        "account": acc.account,
        "role": acc.role,
    }
    # 附带 user_id/member_id 便于后续权限判断
    user = await get_user_by_account_id(db, acc.id)
    if user:
        extra_claims["user_id"] = user.id
    member = await get_member_by_account_id(db, acc.id)
    if member:
        extra_claims["member_id"] = member.id

    token = create_access_token(expires_delta=access_token_expires, extra_claims=extra_claims)

    return TokenResponse(access_token=token, role=acc.role, account=Account.model_validate(acc))


class RegisterRequest(BaseModel):
    """注册请求体（主账号）

    必填字段: account(登录名), password(密码), phone(手机号)
    可选字段: name, gender, email, avatar
    说明: 不需要填写 role，默认为 owner
    手机号格式: 11 位中国大陆手机号, 以 1 开头
    """
    account: str
    password: str
    phone: str  # 手机号，在方法中手动验证格式
    name: str | None = None
    gender: AccountGender | None = None
    email: str | None = None
    avatar: str | None = None


@router.post("/register", response_model=Account)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册主账号：固定创建 owner 账号并生成对应 user 记录

    必填: account, password, phone
    可选: name, gender, email, avatar
    """
    # 手机号格式校验
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, req.phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    
    # 唯一性校验
    exists = await get_account_by_account_name(db, req.account)
    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")

    # 手机号唯一性
    phone_exists = await get_account_by_phone(db, req.phone)
    if phone_exists:
        raise HTTPException(status_code=400, detail="手机号已被使用")

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
                raise HTTPException(status_code=400, detail="邮箱已被使用")

    acc = await create_account(
        db,
        AccountCreate(
            account=req.account,
            password=req.password,
            phone=req.phone,
            name=req.name,
            gender=req.gender,  # type: ignore[arg-type]
            email=norm_email,
            avatar=req.avatar,
            role=AccountRole.owner,
        ),
    )

    # 创建 user（owner 对应记录）
    await create_user(db, user=type("UserCreate", (), {"account_id": acc.id})())

    return Account.model_validate(acc)

