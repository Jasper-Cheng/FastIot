from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

class DeviceParamBase(BaseModel):
    device_id: int
    params: Dict[str, Any]

class DeviceParamCreate(DeviceParamBase):
    pass

class DeviceParamUpdate(BaseModel):
    params: Dict[str, Any]

class DeviceParamInDB(DeviceParamBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True

class DeviceParam(DeviceParamInDB):
    pass
