from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class DeviceMessageStatus(str, Enum):
    new = "new"
    read = "read"

class DeviceMessageLevel(str, Enum):
    low = "low"       # 低
    medium = "medium" # 中
    high = "high"     # 高

class DeviceMessageBase(BaseModel):
    device_id: int
    level: DeviceMessageLevel
    message: Optional[str] = None

class DeviceMessageCreate(DeviceMessageBase):
    pass

class DeviceMessageUpdate(BaseModel):
    level: Optional[DeviceMessageLevel] = None
    message: Optional[str] = None
    status: Optional[DeviceMessageStatus] = None

class DeviceMessageInDB(DeviceMessageBase):
    id: int
    status: DeviceMessageStatus
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceMessage(DeviceMessageInDB):
    pass
