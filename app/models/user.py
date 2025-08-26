from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    user = "user"
    admin = "admin"

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.user

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None

class UserInDB(UserBase):
    id: int
    role: UserRole
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class User(UserInDB):
    pass

class UserLogin(BaseModel):
    username: str
    password: str
