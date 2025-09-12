from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from app.db.base import Base

class Alert(Base):
    __tablename__ = "alert"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(Enum('low', 'medium', 'high', name='alert_level'), nullable=False)
    status = Column(Enum('new', 'read', 'resolved', name='alert_status'), default='new')
    message = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<Alert(id={self.id}, device_id={self.device_id}, level='{self.level}', status='{self.status}')>"
