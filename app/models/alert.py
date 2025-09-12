from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AlertStatus(str, Enum):
    new = "new"
    read = "read"
    resolved = "resolved"

class AlertLevel(str, Enum):
    low = "low"       # 低
    medium = "medium" # 中
    high = "high"     # 高

class AlertBase(BaseModel):
    device_id: int
    level: AlertLevel
    message: Optional[str] = None

class AlertCreate(AlertBase):
    pass

class AlertUpdate(BaseModel):
    level: Optional[AlertLevel] = None
    message: Optional[str] = None
    status: Optional[AlertStatus] = None

class AlertInDB(AlertBase):
    id: int
    status: AlertStatus
    created_at: datetime

    class Config:
        from_attributes = True

class Alert(AlertInDB):
    pass
