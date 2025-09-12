from sqlalchemy import Column, BigInteger, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class DeviceLog(Base):
    __tablename__ = "device_log"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50))
    params = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DeviceLog(id={self.id}, device_id={self.device_id}, event_type='{self.event_type}', created_at='{self.created_at}')>"
