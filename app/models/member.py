from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.account import Account, AccountGender

class MemberBase(BaseModel):
    user_id: int
    account_id: int

class MemberCreate(MemberBase):
    pass

class MemberUpdate(BaseModel):
    pass  # 成员信息通过 account 表管理

class MemberInDB(MemberBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Member(MemberInDB):
    account: Optional[Account] = None


class MemberRegisterRequest(BaseModel):
    """创建成员（子账号）请求

    必填: user_id(归属主账号), account(登录名), password(密码), phone(手机号)
    可选: name, gender, email, avatar
    说明: role 不可填写，强制为 member
    """
    user_id: int
    account: str
    password: str
    phone: str
    name: str | None = None
    gender: Optional[AccountGender] = None
    email: str | None = None
    avatar: str | None = None


class MemberUpdateRequest(BaseModel):
    """更新成员信息请求（更新 account 数据）

    可选字段：account, name, gender, phone, email, avatar, password
    注意：提供至少一个字段
    """
    account: str | None = None
    name: str | None = None
    gender: Optional[AccountGender] = None
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    password: str | None = None
