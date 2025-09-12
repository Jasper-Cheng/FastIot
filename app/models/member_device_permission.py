from pydantic import BaseModel
from typing import Optional

class MemberDevicePermissionBase(BaseModel):
    member_id: int
    device_id: int
    can_control: bool = False

class MemberDevicePermissionCreate(MemberDevicePermissionBase):
    pass

class MemberDevicePermissionUpdate(BaseModel):
    can_control: Optional[bool] = None

class MemberDevicePermissionInDB(MemberDevicePermissionBase):
    id: int

    class Config:
        from_attributes = True

class MemberDevicePermission(MemberDevicePermissionInDB):
    pass
