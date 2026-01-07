from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class OperationTypeEnum(str, Enum):
    login = "login"
    logout = "logout"
    register = "register"
    account_delete = "account_delete"
    account_update = "account_update"
    device_create = "device_create"
    device_update = "device_update"
    device_delete = "device_delete"
    device_bind = "device_bind"
    device_unbind = "device_unbind"
    device_name_update = "device_name_update"
    device_add_to_family = "device_add_to_family"
    device_remove_from_family = "device_remove_from_family"
    family_create = "family_create"
    family_update = "family_update"
    family_delete = "family_delete"
    family_member_add = "family_member_add"
    family_member_remove = "family_member_remove"
    family_member_update = "family_member_update"
    permission_update = "permission_update"
    quick_control = "quick_control"
    feedback_create = "feedback_create"
    feedback_reply = "feedback_reply"
    feedback_status_update = "feedback_status_update"
    notice_create = "notice_create"
    notice_update = "notice_update"
    notice_delete = "notice_delete"
    notice_publish = "notice_publish"
    device_model_create = "device_model_create"
    device_model_update = "device_model_update"
    device_model_delete = "device_model_delete"
    thing_model_create = "thing_model_create"
    thing_model_update = "thing_model_update"
    thing_model_delete = "thing_model_delete"
    thing_model_publish = "thing_model_publish"
    version_create = "version_create"
    version_update = "version_update"
    version_delete = "version_delete"
    version_publish = "version_publish"
    points_adjust = "points_adjust"
    points_deduct = "points_deduct"

class UserOperationLogBase(BaseModel):
    operation_type: OperationTypeEnum = Field(..., description="操作类型")
    description: str = Field(..., max_length=500, description="操作描述")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展信息")

class UserOperationLogCreate(UserOperationLogBase):
    pass

class UserOperationLogUpdate(BaseModel):
    operation_type: Optional[OperationTypeEnum] = None
    description: Optional[str] = Field(None, max_length=500)
    extra: Optional[Dict[str, Any]] = None

class UserOperationLog(UserOperationLogBase):
    id: int
    account_id: int = Field(..., description="操作用户账号ID")
    created_at: datetime

    class Config:
        from_attributes = True
