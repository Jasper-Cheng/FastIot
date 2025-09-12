from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class DeviceLogBase(BaseModel):
    device_id: int
    event_type: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

class DeviceLogCreate(DeviceLogBase):
    pass

class DeviceLogUpdate(BaseModel):
    event_type: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

class DeviceLogInDB(DeviceLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceLog(DeviceLogInDB):
    pass
