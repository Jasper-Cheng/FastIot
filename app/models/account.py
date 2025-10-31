from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class AccountRole(str, Enum):
    owner = "owner"
    member = "member"
    admin = "admin"

class AccountGender(str, Enum):
    male = "male"
    female = "female"
    other = "other"

class AccountBase(BaseModel):
    account: str
    name: Optional[str] = None
    gender: Optional[AccountGender] = AccountGender.other
    phone: str
    email: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[AccountRole] = AccountRole.member

class AccountCreate(AccountBase):
    password: str

class AccountUpdate(BaseModel):
    account: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[AccountGender] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    password: Optional[str] = None

class AccountInDB(AccountBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Account(AccountInDB):
    pass


class LoginRequest(BaseModel):
    """登录请求"""
    account: str
    password: str


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    role: AccountRole
    account: Account
    id: int | None = None  # 统一的用户ID（admin/owner/member的真正ID）


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
