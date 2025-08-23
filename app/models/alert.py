from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AlertStatus(str, Enum):
    new = "new"
    read = "read"
    resolved = "resolved"

class AlertBase(BaseModel):
    device_id: int
    alert_type: str
    message: str

class AlertCreate(AlertBase):
    pass

class AlertUpdate(BaseModel):
    alert_type: Optional[str] = None
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
