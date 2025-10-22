from sqlalchemy import Column, BigInteger, String, Enum, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Account(Base):
    __tablename__ = "account"
    
    id = Column(BigInteger, primary_key=True, index=True)
    account = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    name = Column(String(64), nullable=True)
    gender = Column(Enum('male', 'female', 'other', name='gender_enum'), default='other')
    phone = Column(String(32), unique=True, nullable=False)
    email = Column(String(128), unique=True, nullable=True)
    avatar = Column(String(255), nullable=True)
    role = Column(Enum('owner', 'member', 'admin', name='role_enum'), nullable=False, default='member')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="account", uselist=False, passive_deletes=True)
    member = relationship("Member", back_populates="account", uselist=False, passive_deletes=True)
    admin = relationship("Admin", back_populates="account", uselist=False, passive_deletes=True)
    check_ins = relationship("CheckIn", back_populates="account", passive_deletes=True)
    points = relationship("Points", back_populates="account", passive_deletes=True)
    feedbacks = relationship("Feedback", back_populates="account", passive_deletes=True)
    
    def __repr__(self):
        return f"<Account(id={self.id}, account={self.account}, name={self.name}, role={self.role})>"
