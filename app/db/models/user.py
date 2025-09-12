from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "user"
    
    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("account.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    account = relationship("Account", back_populates="user")
    members = relationship("Member", back_populates="user", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="user", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, account_id={self.account_id})>"
