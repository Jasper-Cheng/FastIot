from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class UserOperationLog(Base):
    """用户操作记录表"""
    __tablename__ = "user_operation_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="操作记录ID")
    account_id = Column(BigInteger, ForeignKey('account.id', ondelete='CASCADE'), nullable=False, comment="操作用户账号ID")
    operation_type = Column(Enum('login','logout','register','account_delete','account_update','device_create','device_update','device_delete','device_bind','device_unbind','device_name_update','device_add_to_family','device_remove_from_family','family_create','family_update','family_delete','family_member_add','family_member_remove','family_member_update','permission_update','quick_control','feedback_create','feedback_reply','feedback_status_update','notice_create','notice_update','notice_delete','notice_publish','device_model_create','device_model_update','device_model_delete','thing_model_create','thing_model_update','thing_model_delete','thing_model_publish','version_create','version_update','version_delete','version_publish','points_adjust','points_deduct', name='operation_type_enum'),
                           nullable=False, comment="操作类型")
    description = Column(String(500), nullable=False, comment="操作描述")
    extra = Column(JSON, nullable=True, comment="扩展信息（如快捷控制的具体操作、设备排序详情等）")
    created_at = Column(DateTime, default=func.now(), comment="操作时间")

    # 关系
    account = relationship("Account", back_populates="operation_logs")

    def __repr__(self):
        return f"<UserOperationLog(id={self.id}, account_id={self.account_id}, operation_type='{self.operation_type}')>"
