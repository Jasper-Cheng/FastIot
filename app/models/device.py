from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class DeviceStatus(str, Enum):
    online = "online"
    offline = "offline"

class DeviceBase(BaseModel):
    name: str
    serial_number: str

class DeviceCreate(DeviceBase):
    owner_id: int

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[DeviceStatus] = None
    last_active: Optional[datetime] = None

class DeviceInDB(DeviceBase):
    id: int
    owner_id: int
    status: DeviceStatus
    last_active: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class Device(DeviceInDB):
    pass

class DeviceDataBase(BaseModel):
    device_id: int
    data: Dict[str, Any]

class DeviceDataCreate(DeviceDataBase):
    pass

class DeviceDataInDB(DeviceDataBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class DeviceData(DeviceDataInDB):
    pass
