from sqlalchemy import Column, BigInteger, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class Device(Base):
    __tablename__ = "device"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(BigInteger, ForeignKey("device_model.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sn = Column(String(100), unique=True, index=True, nullable=False)
    status = Column(Enum('online', 'offline', name='device_status'), default='offline')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Device(id={self.id}, name='{self.name}', sn='{self.sn}', status='{self.status}')>"
