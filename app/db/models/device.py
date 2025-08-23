from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class Device(Base):
    __tablename__ = "Device"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("User.id"))
    status = Column(Enum('online', 'offline', name='device_status'), default='offline')
    last_active = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Device(id={self.id}, name='{self.name}', serial_number='{self.serial_number}', status='{self.status}')>"
