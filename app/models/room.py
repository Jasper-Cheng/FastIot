from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class RoomBase(BaseModel):
    name: str

class RoomCreate(RoomBase):
    pass

class RoomInDB(RoomBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Room(RoomInDB):
    pass
