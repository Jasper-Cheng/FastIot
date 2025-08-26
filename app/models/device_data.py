from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class DeviceDataBase(BaseModel):
    device_id: int
    data: Dict[str, Any]

class DeviceDataCreate(DeviceDataBase):
    pass

class DeviceDataUpdate(BaseModel):
    data: Optional[Dict[str, Any]] = None

class DeviceDataInDB(DeviceDataBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class DeviceData(DeviceDataInDB):
    pass
