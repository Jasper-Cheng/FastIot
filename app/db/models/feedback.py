from sqlalchemy import Column, BigInteger, String, Text, Boolean, DateTime, JSON, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base


class Feedback(Base):
    """意见反馈表"""
    __tablename__ = "feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="反馈ID")
    account_id = Column(BigInteger, ForeignKey('account.id', ondelete='CASCADE'), nullable=False, comment="反馈用户账号ID")
    type = Column(Enum('bug', 'feature', 'improvement', 'complaint', 'praise', 'other', name='feedback_type_enum'), 
                 nullable=False, default='other', comment="反馈类型：bug/功能建议/改进建议/投诉/表扬/其他")
    title = Column(String(255), nullable=False, comment="反馈标题")
    content = Column(Text, nullable=False, comment="反馈内容")
    priority = Column(Enum('low', 'normal', 'high', 'urgent', name='priority_enum'), 
                     nullable=False, default='normal', comment="优先级：低/普通/高/紧急")
    status = Column(Enum('pending', 'processing', 'resolved', 'rejected', 'closed', name='status_enum'), 
                   nullable=False, default='pending', comment="处理状态：待处理/处理中/已解决/已拒绝/已关闭")
    source = Column(Enum('app', 'web', 'email', 'phone', 'wechat', 'other', name='source_enum'), 
                   nullable=False, default='app', comment="来源：app/web/email/phone/wechat/other")
    contact_info = Column(String(255), nullable=True, comment="联系方式")
    replay = Column(Text, nullable=True, comment="回复内容")
    processed_at = Column(DateTime, nullable=True, comment="处理时间")
    extra = Column(JSON, nullable=True, comment="扩展信息")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="更新时间")

    # 关系
    account = relationship("Account", back_populates="feedbacks")
