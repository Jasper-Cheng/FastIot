from pydantic import BaseModel, EmailStr
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
    name: str
    gender: Optional[AccountGender] = AccountGender.other
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None
    role: AccountRole

class AccountCreate(AccountBase):
    password: str

class AccountUpdate(BaseModel):
    account: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[AccountGender] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
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
