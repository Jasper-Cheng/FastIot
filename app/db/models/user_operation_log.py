from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class UserOperationLog(Base):
    """用户操作记录表"""
    __tablename__ = "user_operation_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="操作记录ID")
    account_id = Column(BigInteger, ForeignKey('account.id', ondelete='CASCADE'), nullable=False, comment="操作用户账号ID")
    operation_type = Column(Enum('login','logout','register','user_add','user_delete','user_update','device_add','device_delete','room_add','room_delete','room_device_sort','member_add','member_delete','member_update','feedback','permission_update','system_update','quick_control', name='operation_type_enum'),
                           nullable=False, comment="操作类型")
    description = Column(String(500), nullable=False, comment="操作描述")
    result = Column(Enum('success','failure', name='result_enum'), nullable=False, default='success', comment="操作结果")
    error_message = Column(Text, nullable=True, comment="错误信息（操作失败时）")
    extra = Column(JSON, nullable=True, comment="扩展信息（如快捷控制的具体操作、设备排序详情等）")
    created_at = Column(DateTime, default=func.now(), comment="操作时间")

    # 关系
    account = relationship("Account", back_populates="operation_logs")

    def __repr__(self):
        return f"<UserOperationLog(id={self.id}, account_id={self.account_id}, operation_type='{self.operation_type}', result='{self.result}')>"
