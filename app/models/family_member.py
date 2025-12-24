from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum
from app.models.account import Account

class FamilyMemberRole(str, Enum):
    creator = "creator"
    member = "member"

class FamilyMemberBase(BaseModel):
    family_id: int
    account_id: int
    role: FamilyMemberRole = FamilyMemberRole.member
    nickname: Optional[str] = None

class FamilyMemberCreate(FamilyMemberBase):
    pass

class FamilyMemberUpdate(BaseModel):
    nickname: Optional[str] = None

class JoinFamilyRequest(BaseModel):
    """加入家庭请求"""
    nickname: Optional[str] = None  # 在家庭中的昵称，不提供则使用账号的nickname

class JoinByInviteCodeRequest(BaseModel):
    """通过邀请码加入家庭请求"""
    invite_code: str  # 家庭邀请码
    nickname: Optional[str] = None  # 在家庭中的昵称

class FamilyMemberInDB(FamilyMemberBase):
    id: int
    joined_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class FamilyMember(FamilyMemberInDB):
    pass

class FamilyMemberWithAccount(BaseModel):
    """家庭成员信息，包含完整的 account 信息"""
    id: int
    family_id: int
    role: FamilyMemberRole
    nickname: Optional[str] = None
    joined_at: datetime
    created_at: datetime
    account: Account  # 完整的 account 信息，而不是 account_id

    class Config:
        from_attributes = True

