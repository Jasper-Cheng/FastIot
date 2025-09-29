from sqlalchemy import Column, BigInteger, Date, DateTime, Integer, String, Text, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class CheckIn(Base):
    """签到表"""
    __tablename__ = "check_in"

    id = Column(BigInteger, primary_key=True, index=True, comment="签到记录ID")
    account_id = Column(BigInteger, ForeignKey("account.id", ondelete="CASCADE"), nullable=False, comment="签到用户账号ID")
    check_in_date = Column(Date, nullable=False, comment="签到日期")
    check_in_time = Column(DateTime, nullable=False, comment="签到时间")
    points_earned = Column(Integer, default=0, comment="本次签到获得积分")
    continuous_days = Column(Integer, default=1, comment="连续签到天数")
    check_in_type = Column(Enum('normal', 'bonus', 'makeup', name='check_in_type'), default='normal', comment="签到类型：正常/奖励/补签")
    extra = Column(JSON, nullable=True, comment="扩展信息")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    # 关系
    account = relationship("Account", back_populates="check_ins")
