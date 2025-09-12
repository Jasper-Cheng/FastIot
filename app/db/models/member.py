from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Member(Base):
    __tablename__ = "member"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(BigInteger, ForeignKey("account.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="members")
    account = relationship("Account", back_populates="member")
    device_permissions = relationship("MemberDevicePermission", back_populates="member", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Member(id={self.id}, user_id={self.user_id}, account_id={self.account_id})>"
