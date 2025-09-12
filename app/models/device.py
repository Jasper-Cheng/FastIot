from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class DeviceStatus(str, Enum):
    online = "online"
    offline = "offline"

class DeviceBase(BaseModel):
    name: str
    sn: str
    status: DeviceStatus = DeviceStatus.offline

class DeviceCreate(DeviceBase):
    user_id: int
    model_id: int

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    sn: Optional[str] = None
    status: Optional[DeviceStatus] = None

class DeviceInDB(DeviceBase):
    id: int
    user_id: int
    model_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Device(DeviceInDB):
    pass

# 设备控制相关模型
class DeviceControl(BaseModel):
    device_id: int
    command: str
    params: Optional[Dict[str, Any]] = None

class DeviceControlResult(BaseModel):
    success: bool
    message: Optional[str] = None

class DeviceStatusResponse(BaseModel):
    device_id: int
    online: bool
    status: Optional[Dict[str, Any]] = None

class DeviceListResponse(BaseModel):
    devices: List[Device]
    total: int
    online_count: int

# 创建设备时的输入模型
class DeviceCreateInput(BaseModel):
    name: str
    sn: str
    model_id: int