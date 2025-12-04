from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class FamilyDevice(Base):
    """家庭设备关联表：设备与家庭的多对多关系"""
    __tablename__ = "family_device"

    id = Column(BigInteger, primary_key=True, index=True)
    family_id = Column(BigInteger, ForeignKey("family.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    family = relationship("Family", back_populates="family_devices")
    device = relationship("Device", back_populates="family_devices")

    def __repr__(self):
        return f"<FamilyDevice(id={self.id}, family_id={self.family_id}, device_id={self.device_id})>"

