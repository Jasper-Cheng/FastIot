from pydantic import BaseModel
from typing import Optional

class MemberDevicePermissionBase(BaseModel):
    member_id: int
    device_id: int

class MemberDevicePermissionCreate(MemberDevicePermissionBase):
    pass

class MemberDevicePermissionUpdate(BaseModel):
    pass

class MemberDevicePermissionInDB(MemberDevicePermissionBase):
    id: int

    class Config:
        from_attributes = True

class MemberDevicePermission(MemberDevicePermissionInDB):
    pass
