from sqlalchemy import Column, BigInteger, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class FamilyMember(Base):
    __tablename__ = "family_member"
    
    id = Column(BigInteger, primary_key=True, index=True)
    family_id = Column(BigInteger, ForeignKey("family.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(BigInteger, ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum('creator', 'member', name='family_member_role'), nullable=False, default='member')
    nickname = Column(String(64), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    family = relationship("Family", back_populates="members")
    account = relationship("Account", back_populates="family_members")
    
    def __repr__(self):
        return f"<FamilyMember(id={self.id}, family_id={self.family_id}, account_id={self.account_id}, role='{self.role}')>"

