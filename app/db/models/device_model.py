from sqlalchemy import Column, BigInteger, String, DateTime, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class DeviceModel(Base):
    __tablename__ = "device_model"

    id = Column(BigInteger, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    vendor = Column(String(100))
    params = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DeviceModel(id={self.id}, model_name='{self.model_name}', vendor='{self.vendor}')>"
