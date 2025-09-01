from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from app.db.base import Base

class Alert(Base):
    __tablename__ = "Alert"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("Device.id"), nullable=False, index=True)
    alert_type = Column(Enum('emergency', 'important', 'minor', 'reminder', name='alert_type'), nullable=False)
    message = Column(Text)
    status = Column(Enum('new', 'read', 'resolved', name='alert_status'), default='new')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<Alert(id={self.id}, device_id={self.device_id}, alert_type='{self.alert_type}', status='{self.status}')>"
