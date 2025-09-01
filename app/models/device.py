from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class DeviceStatus(str, Enum):
    online = "online"
    offline = "offline"

class DeviceBase(BaseModel):
    name: str
    serial_number: str
    status: DeviceStatus = DeviceStatus.offline
    data: Optional[Dict[str, Any]] = None

class DeviceCreate(DeviceBase):
    owner_id: int

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    serial_number: Optional[str] = None
    status: Optional[DeviceStatus] = None
    data: Optional[Dict[str, Any]] = None

class DeviceInDB(DeviceBase):
    id: int
    owner_id: int
    last_active: Optional[datetime] = None
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
    last_active: Optional[datetime] = None

class DeviceListResponse(BaseModel):
    devices: List[Device]
    total: int
    online_count: int

class DeviceDataBase(BaseModel):
    device_id: int
    data: Dict[str, Any]

class DeviceDataCreate(DeviceDataBase):
    pass

class DeviceDataInDB(DeviceDataBase):
    id: int
    timestamp: datetime

class DeviceData(DeviceDataInDB):
    pass

# 创建设备时的输入模型（不包含 owner_id/description，包含初始 data）
class DeviceCreateInput(BaseModel):
    name: str
    serial_number: str
    data: Dict[str, Any]