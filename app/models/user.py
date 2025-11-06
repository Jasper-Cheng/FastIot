from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.account import Account, AccountGender

class UserBase(BaseModel):
    account_id: int

class UserCreate(UserBase):
    pass

class UserInDB(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class User(UserInDB):
    account: Optional[Account] = None


class UserUpdateRequest(BaseModel):
    """用户信息更新请求
    
    所有字段都是可选的，至少需要提供一个字段进行更新
    """
    nickname: str | None = None
    gender: AccountGender | None = None
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    password: str | None = None
