from pydantic import BaseModel, Field
from typing import Optional, List

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


class MemberPermissionBatchUpdateRequest(BaseModel):
    """批量更新成员权限请求"""
    device_ids: List[int] = Field(..., description="设备ID列表", example=[1, 2, 3])


class MemberPermissionBatchUpdateResponse(BaseModel):
    """批量更新成员权限响应"""
    success: bool = Field(..., description="操作是否成功", example=True)
    message: str = Field(..., description="操作结果消息", example="批量更新成功")
    data: List[MemberDevicePermissionInDB] = Field(..., description="更新后的权限列表")
