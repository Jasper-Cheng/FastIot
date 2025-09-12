from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AccountRole(str, Enum):
    owner = "owner"
    member = "member"

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

class AccountLogin(BaseModel):
    account: str
    password: str
