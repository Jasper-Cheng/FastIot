from sqlalchemy import Column, BigInteger, Integer, ForeignKey, JSON
from app.db.base import Base

class DeviceData(Base):
    __tablename__ = "DeviceData"

    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("Device.id"), nullable=False, index=True)
    data = Column(JSON, nullable=False)

    def __repr__(self):
        return f"<DeviceData(id={self.id}, device_id={self.device_id})>"
