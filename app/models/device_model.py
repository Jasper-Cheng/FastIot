from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class DeviceModelBase(BaseModel):
    model_name: str
    vendor: Optional[str] = None
    params: Dict[str, Any]

class DeviceModelCreate(DeviceModelBase):
    pass

class DeviceModelUpdate(BaseModel):
    model_name: Optional[str] = None
    vendor: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

class DeviceModelInDB(DeviceModelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceModel(DeviceModelInDB):
    pass
