from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class OperationTypeEnum(str, Enum):
    login = "login"
    logout = "logout"
    register = "register"
    user_delete = "user_delete"
    user_update = "user_update"
    device_add = "device_add"
    device_delete = "device_delete"
    room_add = "room_add"
    room_delete = "room_delete"
    room_device_sort = "room_device_sort"
    member_add = "member_add"
    member_delete = "member_delete"
    member_update = "member_update"
    feedback = "feedback"
    permission_update = "permission_update"
    system_update = "system_update"
    quick_control = "quick_control"

class ResultEnum(str, Enum):
    success = "success"
    failure = "failure"

class UserOperationLogBase(BaseModel):
    operation_type: OperationTypeEnum = Field(..., description="操作类型")
    description: str = Field(..., max_length=500, description="操作描述")
    result: ResultEnum = Field(default=ResultEnum.success, description="操作结果")
    error_message: Optional[str] = Field(None, description="错误信息（操作失败时）")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展信息")

class UserOperationLogCreate(UserOperationLogBase):
    pass

class UserOperationLogUpdate(BaseModel):
    operation_type: Optional[OperationTypeEnum] = None
    description: Optional[str] = Field(None, max_length=500)
    result: Optional[ResultEnum] = None
    error_message: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

class UserOperationLog(UserOperationLogBase):
    id: int
    account_id: int = Field(..., description="操作用户账号ID")
    created_at: datetime

    class Config:
        from_attributes = True

class UserOperationLogInDB(UserOperationLog):
    pass
