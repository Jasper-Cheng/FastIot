"""
系统消息模型
"""
from sqlalchemy import Column, BigInteger, String, Text, Enum, DateTime, JSON, Index
from sqlalchemy.sql import func
from app.db.base import Base


class SystemMessage(Base):
    """系统消息表"""
    __tablename__ = "system_message"

    id = Column(BigInteger, primary_key=True, index=True, comment="消息ID")
    title = Column(String(255), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")
    type = Column(
        Enum('notification', 'announcement', 'alert', 'maintenance', 'update', 
             name='system_message_type'),
        nullable=False, 
        default='notification',
        comment="消息类型：通知/公告/警告/维护/更新"
    )
    priority = Column(
        Enum('low', 'normal', 'high', 'urgent', name='system_message_priority'),
        nullable=False,
        default='normal',
        comment="优先级：低/普通/高/紧急"
    )
    platforms = Column(JSON, nullable=False, comment="目标平台：android/ios/web等，可多选")
    extra = Column(JSON, nullable=True, comment="扩展信息")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 索引
    __table_args__ = (
        Index('idx_system_message_type', 'type'),
        Index('idx_system_message_priority', 'priority'),
        Index('idx_system_message_created_at', 'created_at'),
    )
