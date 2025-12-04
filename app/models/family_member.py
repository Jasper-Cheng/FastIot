from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

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

class FamilyMemberInDB(FamilyMemberBase):
    id: int
    joined_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class FamilyMember(FamilyMemberInDB):
    pass

