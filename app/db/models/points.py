from sqlalchemy import Column, BigInteger, DateTime, Integer, String, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Points(Base):
    """积分表"""
    __tablename__ = "points"

    id = Column(BigInteger, primary_key=True, index=True, comment="积分记录ID")
    account_id = Column(BigInteger, ForeignKey("account.id", ondelete="CASCADE"), nullable=False, comment="用户账号ID")
    points = Column(Integer, nullable=False, comment="积分变动数量（正数为增加，负数为减少）")
    balance = Column(Integer, nullable=False, comment="变动后积分余额")
    type = Column(Enum('check_in', 'task', 'reward', 'exchange', 'penalty', 'admin_adjust', name='points_type'), nullable=False, comment="积分类型：签到/任务/奖励/兑换/惩罚/管理员调整")
    description = Column(String(255), nullable=True, comment="积分变动描述")
    extra = Column(JSON, nullable=True, comment="扩展信息")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    # 关系
    account = relationship("Account", back_populates="points")
