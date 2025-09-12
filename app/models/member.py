from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum

class MemberGender(str, Enum):
    male = "male"
    female = "female"
    other = "other"

class MemberBase(BaseModel):
    name: str
    gender: Optional[MemberGender] = None
    account: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None

class MemberCreate(MemberBase):
    user_id: int
    password: Optional[str] = None

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[MemberGender] = None
    account: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None

class MemberInDB(MemberBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Member(MemberInDB):
    pass

class MemberLogin(BaseModel):
    account: str
    password: str
