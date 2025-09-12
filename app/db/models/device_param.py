from sqlalchemy import Column, BigInteger, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class DeviceParam(Base):
    __tablename__ = "device_param"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    params = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DeviceParam(id={self.id}, device_id={self.device_id}, updated_at='{self.updated_at}')>"
