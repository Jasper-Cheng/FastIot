from pydantic import BaseModel, Field
from typing import Optional, List


class RoomDeviceBase(BaseModel):
    room_id: int
    device_id: int
    sort_order: Optional[int] = 0


class RoomDeviceInDB(RoomDeviceBase):
    id: int

    class Config:
        from_attributes = True


class RoomDevice(RoomDeviceInDB):
    pass


class RoomDeviceBatchSortItem(BaseModel):
    """房间设备批量排序项"""
    device_id: int = Field(..., description="设备ID", example=1)
    sort_order: int = Field(..., description="排序号，数值越小排序越靠前", example=0)


class RoomDeviceBatchSortRequest(BaseModel):
    """房间设备批量排序请求"""
    room_id: int = Field(..., description="房间ID", example=1)
    devices: List[RoomDeviceBatchSortItem] = Field(..., description="设备排序列表", example=[
        {"device_id": 1, "sort_order": 0},
        {"device_id": 2, "sort_order": 1},
        {"device_id": 3, "sort_order": 2}
    ])


class RoomDeviceBatchSortResponse(BaseModel):
    """房间设备批量排序响应"""
    success: bool = Field(..., description="操作是否成功", example=True)
    message: str = Field(..., description="操作结果消息", example="批量更新成功")
    data: List[RoomDeviceInDB] = Field(..., description="更新后的房间设备关联列表")


