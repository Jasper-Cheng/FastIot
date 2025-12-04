from sqlalchemy import Column, BigInteger, String, Enum, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Account(Base):
    __tablename__ = "account"
    
    id = Column(BigInteger, primary_key=True, index=True)
    password = Column(String(128), nullable=True)
    nickname = Column(String(64), nullable=True)
    unionid = Column(String(128), unique=True, nullable=True, index=True)
    gender = Column(Enum('male', 'female', 'other', name='gender_enum'), default='other')
    phone = Column(String(32), unique=True, nullable=False)
    email = Column(String(128), unique=True, nullable=True)
    avatar = Column(String(255), nullable=True)
    role = Column(Enum('user', 'admin', name='role_enum'), nullable=False, default='user')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    devices = relationship("Device", foreign_keys="Device.account_id", back_populates="account", passive_deletes=True)
    family_members = relationship("FamilyMember", back_populates="account", passive_deletes=True)
    check_ins = relationship("CheckIn", back_populates="account", passive_deletes=True)
    points = relationship("Points", back_populates="account", passive_deletes=True)
    feedbacks = relationship("Feedback", back_populates="account", passive_deletes=True)
    operation_logs = relationship("UserOperationLog", back_populates="account", passive_deletes=True)
    
    def __repr__(self):
        return f"<Account(id={self.id}, nickname={self.nickname}, role={self.role})>"
