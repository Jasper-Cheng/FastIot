from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AlertStatus(str, Enum):
    new = "new"
    read = "read"
    resolved = "resolved"

class AlertType(str, Enum):
    emergency = "emergency"   # 紧急
    important = "important"   # 重要
    minor = "minor"           # 次要
    reminder = "reminder"     # 提醒

class AlertBase(BaseModel):
    device_id: int
    alert_type: AlertType
    message: str

class AlertCreate(AlertBase):
    pass

class AlertUpdate(BaseModel):
    alert_type: Optional[AlertType] = None
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
