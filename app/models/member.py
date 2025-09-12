from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.account import Account

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
    user: Optional[dict] = None  # 避免循环导入
