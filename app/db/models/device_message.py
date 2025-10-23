from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class DeviceMessage(Base):
    __tablename__ = "device_message"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(Enum('low', 'normal', 'error', 'fatal', name='device_message_level'), nullable=False, default='low')
    status = Column(Enum('new', 'read', name='device_message_status'), default='new')
    message = Column(String(255))
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self):
        return f"<DeviceMessage(id={self.id}, device_id={self.device_id}, level='{self.level}', status='{self.status}')>"
