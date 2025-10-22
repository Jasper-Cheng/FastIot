from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class FeedbackTypeEnum(str, Enum):
    bug = "bug"
    feature = "feature"
    improvement = "improvement"
    complaint = "complaint"
    praise = "praise"
    other = "other"


class PriorityEnum(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class StatusEnum(str, Enum):
    pending = "pending"
    processing = "processing"
    resolved = "resolved"
    rejected = "rejected"
    closed = "closed"


class SourceEnum(str, Enum):
    app = "app"
    web = "web"
    email = "email"
    phone = "phone"
    wechat = "wechat"
    other = "other"


class FeedbackBase(BaseModel):
    account_id: int = Field(..., description="反馈用户账号ID")
    type: FeedbackTypeEnum = Field(default=FeedbackTypeEnum.other, description="反馈类型")
    title: str = Field(..., description="反馈标题")
    content: str = Field(..., description="反馈内容")
    priority: PriorityEnum = Field(default=PriorityEnum.normal, description="优先级")
    source: SourceEnum = Field(default=SourceEnum.app, description="来源")
    contact_info: Optional[str] = Field(None, description="联系方式")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展信息")


class FeedbackCreate(FeedbackBase):
    pass


class FeedbackUpdate(BaseModel):
    type: Optional[FeedbackTypeEnum] = None
    title: Optional[str] = None
    content: Optional[str] = None
    priority: Optional[PriorityEnum] = None
    status: Optional[StatusEnum] = None
    source: Optional[SourceEnum] = None
    contact_info: Optional[str] = None
    replay: Optional[str] = None
    processed_at: Optional[datetime] = None
    extra: Optional[Dict[str, Any]] = None


class Feedback(FeedbackBase):
    id: int
    status: StatusEnum = Field(default=StatusEnum.pending, description="处理状态")
    replay: Optional[str] = Field(None, description="回复内容")
    processed_at: Optional[datetime] = Field(None, description="处理时间")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
