from pydantic import BaseModel
from typing import Optional


class RoomDeviceBase(BaseModel):
    room_id: int
    device_id: int
    sort_order: Optional[int] = 0


class RoomDeviceCreate(RoomDeviceBase):
    pass


class RoomDeviceUpdate(BaseModel):
    sort_order: Optional[int] = None


class RoomDeviceInDB(RoomDeviceBase):
    id: int

    class Config:
        from_attributes = True


class RoomDevice(RoomDeviceInDB):
    pass


