from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class DeviceThingModelBase(BaseModel):
    name: str
    description: Optional[str] = None
    properties: Dict[str, Any]
    services: List[str]
    events: List[str]

class DeviceThingModelCreate(DeviceThingModelBase):
    pass

class DeviceThingModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    services: Optional[List[str]] = None
    events: Optional[List[str]] = None

class DeviceThingModelInDB(DeviceThingModelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceThingModel(DeviceThingModelInDB):
    pass
