from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class DeviceMessageStatus(str, Enum):
    new = "new"
    read = "read"

class DeviceMessageLevel(str, Enum):
    normal = "normal"   # 正常
    error = "error"     # 错误
    fatal = "fatal"     # 致命

class DeviceMessageBase(BaseModel):
    device_id: int
    level: DeviceMessageLevel
    message: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None

class DeviceMessageCreate(DeviceMessageBase):
    pass

class DeviceMessageUpdate(BaseModel):
    level: Optional[DeviceMessageLevel] = None
    message: Optional[str] = None
    status: Optional[DeviceMessageStatus] = None
    detail: Optional[Dict[str, Any]] = None

class DeviceMessageInDB(DeviceMessageBase):
    id: int
    status: DeviceMessageStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DeviceMessage(DeviceMessageInDB):
    pass
