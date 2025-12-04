from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class DeviceStatus(str, Enum):
    unconfigured = "unconfigured"  # 未配网
    configured = "configured"      # 已配网
    unbound = "unbound"            # 未绑定
    bound = "bound"                # 已绑定
    offline = "offline"            # 离线
    online = "online"              # 在线
    fault = "fault"                # 故障

class DeviceBase(BaseModel):
    name: str
    sn: str
    status: DeviceStatus = DeviceStatus.unconfigured

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    sn: Optional[str] = None
    status: Optional[DeviceStatus] = None
    account_id: Optional[int] = None

class DeviceInDB(DeviceBase):
    id: int
    account_id: Optional[int] = None
    model_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Device(DeviceInDB):
    pass

# 设备名称更新模型
class DeviceNameUpdate(BaseModel):
    name: str


# 设备绑定请求模型（通过序列号）
class DeviceBindBySNRequest(BaseModel):
    sn: str