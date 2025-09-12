from sqlalchemy import Column, BigInteger, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import TINYINT
from app.db.base import Base

class MemberDevicePermission(Base):
    __tablename__ = "member_device_permission"

    id = Column(BigInteger, primary_key=True, index=True)
    member_id = Column(BigInteger, ForeignKey("member.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    can_control = Column(TINYINT(1), default=0)  # 0 = False, 1 = True

    __table_args__ = (
        UniqueConstraint('member_id', 'device_id', name='unique_member_device'),
    )

    def __repr__(self):
        return f"<MemberDevicePermission(id={self.id}, member_id={self.member_id}, device_id={self.device_id}, can_control={self.can_control})>"
