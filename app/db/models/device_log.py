from sqlalchemy import Column, BigInteger, String, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.sql import func
from app.db.base import Base

class DeviceLog(Base):
    __tablename__ = "device_log"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum('properties', 'services', 'events', name='device_log_type'), nullable=False)
    params = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DeviceLog(id={self.id}, device_id={self.device_id}, type='{self.type}', created_at='{self.created_at}')>"
