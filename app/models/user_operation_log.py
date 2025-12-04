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
    device_bind = "device_bind"
    device_unbind = "device_unbind"
    family_create = "family_create"
    family_delete = "family_delete"
    family_member_add = "family_member_add"
    family_member_remove = "family_member_remove"
    family_member_update = "family_member_update"
    permission_update = "permission_update"
    quick_control = "quick_control"

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

class UserOperationLogInDB(UserOperationLog):
    pass
