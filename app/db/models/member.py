from sqlalchemy import Column, BigInteger, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class Member(Base):
    __tablename__ = "member"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    gender = Column(Enum('male', 'female', 'other', name='member_gender'))
    account = Column(String(50), unique=True, index=True)
    password = Column(String(255))
    phone = Column(String(20))
    email = Column(String(100))
    avatar = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Member(id={self.id}, name='{self.name}', account='{self.account}', user_id={self.user_id})>"
