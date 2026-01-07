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


class StatusEnum(str, Enum):
    pending = "pending"
    processing = "processing"
    resolved = "resolved"
    rejected = "rejected"
    closed = "closed"


class SourceEnum(str, Enum):
    web = "web"
    app = "app"


class FeedbackBase(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="反馈人姓名（可选）")
    type: FeedbackTypeEnum = Field(default=FeedbackTypeEnum.other, description="反馈类型")
    content: str = Field(..., description="反馈内容")
    contact_info: Optional[str] = Field(None, description="联系方式")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展信息")


class FeedbackCreate(FeedbackBase):
    pass


class FeedbackUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="反馈人姓名（可选）")
    type: Optional[FeedbackTypeEnum] = None
    content: Optional[str] = None
    status: Optional[StatusEnum] = None
    source: Optional[SourceEnum] = None
    contact_info: Optional[str] = None
    replay: Optional[str] = None
    processed_at: Optional[datetime] = None
    extra: Optional[Dict[str, Any]] = None


class Feedback(FeedbackBase):
    id: int
    account_id: int = Field(..., description="反馈用户账号ID")
    status: StatusEnum = Field(default=StatusEnum.pending, description="处理状态")
    source: SourceEnum = Field(..., description="来源")
    replay: Optional[str] = Field(None, description="回复内容")
    processed_at: Optional[datetime] = Field(None, description="处理时间")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
