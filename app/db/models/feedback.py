from sqlalchemy import Column, BigInteger, String, Text, Boolean, DateTime, JSON, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Feedback(Base):
    """意见反馈表"""
    __tablename__ = "feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="反馈ID")
    account_id = Column(BigInteger, ForeignKey('account.id', ondelete='CASCADE'), nullable=False, comment="反馈用户账号ID")
    name = Column(String(100), nullable=True, comment="反馈人姓名（可选）")
    type = Column(Enum('bug', 'feature', 'improvement', 'complaint', 'praise', 'other', name='feedback_type_enum'),
                 nullable=False, default='other', comment="反馈类型：bug/功能建议/改进建议/投诉/表扬/其他")
    content = Column(Text, nullable=False, comment="反馈内容")
    status = Column(Enum('pending', 'processing', 'resolved', 'rejected', 'closed', name='status_enum'),
                   nullable=False, default='pending', comment="处理状态：待处理/处理中/已解决/已拒绝/已关闭")
    source = Column(Enum('web', 'app', name='source_enum'),
                   nullable=False, default='web', comment="来源：web或app")
    contact_info = Column(String(255), nullable=True, comment="联系方式")
    replay = Column(Text, nullable=True, comment="回复内容")
    processed_at = Column(DateTime, nullable=True, comment="处理时间")
    extra = Column(JSON, nullable=True, comment="扩展信息")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="更新时间")

    # 关系
    account = relationship("Account", back_populates="feedbacks")
