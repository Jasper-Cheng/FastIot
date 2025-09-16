from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class DeviceModelBase(BaseModel):
    model_code: str
    name: str
    vendor: Optional[str] = None
    thing_model_id: int
    params: Dict[str, Any]

class DeviceModelCreate(DeviceModelBase):
    pass

class DeviceModelUpdate(BaseModel):
    model_code: Optional[str] = None
    name: Optional[str] = None
    vendor: Optional[str] = None
    thing_model_id: Optional[int] = None
    params: Optional[Dict[str, Any]] = None

class DeviceModelInDB(DeviceModelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceModel(DeviceModelInDB):
    pass
