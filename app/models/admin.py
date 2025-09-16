from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.account import Account


class AdminBase(BaseModel):
    account_id: int


class AdminInDB(AdminBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Admin(AdminInDB):
    account: Optional[Account] = None


