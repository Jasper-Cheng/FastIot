from sqlalchemy import Column, BigInteger, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class DeviceData(Base):
    __tablename__ = "DeviceData"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("Device.id"), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<DeviceData(id={self.id}, device_id={self.device_id}, timestamp='{self.timestamp}')>"
