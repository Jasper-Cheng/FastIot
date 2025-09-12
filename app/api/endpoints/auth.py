from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Literal
from pydantic import BaseModel

from app.db.session import get_db
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.account import (
    get_account_by_account_name,
    get_account_by_phone,
    create_account,
)
from app.crud.user import create_user, get_user_by_account_id
from app.crud.member import create_member, get_member_by_account_id
from app.models.account import AccountCreate, AccountLogin, Account, AccountRole

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    role: AccountRole
    account: Account

class LoginRequest(BaseModel):
    account: str | None = None
    phone: str | None = None
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """统一账号登录：支持 账号+密码 或 手机号+密码"""
    if bool(payload.account) == bool(payload.phone):  # 两者必须且只能提供一个
        raise HTTPException(status_code=400, detail="请提供账号或手机号中的一个")

    # 获取账号记录
    acc = None
    if payload.account:
        acc = await get_account_by_account_name(db, payload.account)
    else:
        acc = await get_account_by_phone(db, payload.phone or "")

    if not acc or not verify_password(payload.password, acc.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "user_type": "account",
        "account_id": account.id,
        "account": account.account,
        "role": account.role,
    }
    # 附带 user_id/member_id 便于后续权限判断
    user = await get_user_by_account_id(db, account.id)
    if user:
        extra_claims["user_id"] = user.id
    member = await get_member_by_account_id(db, account.id)
    if member:
        extra_claims["member_id"] = member.id

    token = create_access_token(expires_delta=access_token_expires, extra_claims=extra_claims)

    return TokenResponse(access_token=token, role=acc.role, account=Account.model_validate(acc))


class RegisterRequest(BaseModel):
    account: AccountCreate


@router.post("/register", response_model=Account)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册账号：根据 role 创建对应 user 或 member 记录"""
    # 唯一性校验
    exists = await get_account_by_account_name(db, req.account.account)
    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")

    acc = await create_account(db, req.account)

    if acc.role == AccountRole.owner:
        # 创建 user
        await create_user(db, user=type("UserCreate", (), {"account_id": acc.id})())
    else:
        # 需要归属的主账号，由外部流程创建 member 更合理；此处简单跳过
        pass

    return Account.model_validate(acc)

