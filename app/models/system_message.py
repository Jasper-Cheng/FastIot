"""
系统消息Pydantic模型
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class SystemMessageType(str, Enum):
    """系统消息类型枚举"""
    NOTIFICATION = "notification"
    ANNOUNCEMENT = "announcement"
    ALERT = "alert"
    MAINTENANCE = "maintenance"
    UPDATE = "update"


class SystemMessagePriority(str, Enum):
    """系统消息优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SystemMessageBase(BaseModel):
    """系统消息基础模型"""
    title: str = Field(..., description="消息标题", max_length=255)
    content: str = Field(..., description="消息内容")
    type: SystemMessageType = Field(default=SystemMessageType.NOTIFICATION, description="消息类型")
    priority: SystemMessagePriority = Field(default=SystemMessagePriority.NORMAL, description="优先级")
    platforms: List[str] = Field(..., description="目标平台：web或app，可多选")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展信息")


class SystemMessageCreate(SystemMessageBase):
    """创建系统消息模型"""
    pass


class SystemMessageUpdate(BaseModel):
    """更新系统消息模型"""
    title: Optional[str] = Field(None, description="消息标题", max_length=255)
    content: Optional[str] = Field(None, description="消息内容")
    type: Optional[SystemMessageType] = Field(None, description="消息类型")
    priority: Optional[SystemMessagePriority] = Field(None, description="优先级")
    platforms: Optional[List[str]] = Field(None, description="目标平台：web或app，可多选")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展信息")


class SystemMessageInDB(SystemMessageBase):
    """数据库中的系统消息模型"""
    id: int = Field(..., description="消息ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class SystemMessage(SystemMessageInDB):
    """系统消息响应模型"""
    pass


class SystemMessageList(BaseModel):
    """系统消息列表响应模型"""
    items: list[SystemMessage] = Field(..., description="消息列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页数量")
    pages: int = Field(..., description="总页数")
