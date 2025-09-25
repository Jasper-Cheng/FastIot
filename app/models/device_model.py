from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class DeviceModelBase(BaseModel):
    model_code: str
    name: str
    vendor: Optional[str] = None
    thing_model_id: int
    properties: Dict[str, Any]
    services: List[str]
    events: List[str]

class DeviceModelCreate(DeviceModelBase):
    pass

class DeviceModelUpdate(BaseModel):
    model_code: Optional[str] = None
    name: Optional[str] = None
    vendor: Optional[str] = None
    thing_model_id: Optional[int] = None
    properties: Optional[Dict[str, Any]] = None
    services: Optional[List[str]] = None
    events: Optional[List[str]] = None

class DeviceModelInDB(DeviceModelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceModel(DeviceModelInDB):
    pass
