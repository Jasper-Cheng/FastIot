from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.account import Account

class UserBase(BaseModel):
    account_id: int

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    pass  # 用户信息通过 account 表管理

class UserInDB(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class User(UserInDB):
    account: Optional[Account] = None
