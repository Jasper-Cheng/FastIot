from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.account import Account, AccountGender

class MemberBase(BaseModel):
    user_id: int
    account_id: int

class MemberCreate(MemberBase):
    pass

class MemberInDB(MemberBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Member(MemberInDB):
    account: Optional[Account] = None


class MemberRegisterRequest(BaseModel):
    """创建成员（子账号）请求

    必填: phone(手机号)
    可选: password(密码), nickname, gender, email, avatar
    说明: role 不可填写，强制为 member；user_id 从当前登录的 owner 的 token 中获取
    """
    phone: str
    password: str | None = None
    nickname: str | None = None
    gender: Optional[AccountGender] = None
    email: str | None = None
    avatar: str | None = None


class MemberUpdateRequest(BaseModel):
    """更新成员信息请求（更新 account 数据）

    可选字段：nickname, gender, phone, email, avatar, password
    注意：提供至少一个字段
    """
    nickname: str | None = None
    gender: Optional[AccountGender] = None
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    password: str | None = None
