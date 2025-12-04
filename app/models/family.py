from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FamilyBase(BaseModel):
    name: str
    avatar: Optional[str] = None
    description: Optional[str] = None

class FamilyCreate(FamilyBase):
    pass

class FamilyUpdate(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    description: Optional[str] = None

class FamilyInDB(FamilyBase):
    id: int
    invite_code: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Family(FamilyInDB):
    pass

