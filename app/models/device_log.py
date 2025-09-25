from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class DeviceLogType(str, Enum):
    properties = "properties"  # 属性相关事件
    services = "services"      # 服务相关事件
    events = "events"          # 事件相关事件

class DeviceLogBase(BaseModel):
    device_id: int
    type: DeviceLogType
    params: Optional[Dict[str, Any]] = None

class DeviceLogCreate(DeviceLogBase):
    pass

class DeviceLogUpdate(BaseModel):
    type: Optional[DeviceLogType] = None
    params: Optional[Dict[str, Any]] = None

class DeviceLogInDB(DeviceLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceLog(DeviceLogInDB):
    pass
