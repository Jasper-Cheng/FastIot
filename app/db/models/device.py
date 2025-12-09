from sqlalchemy import Column, BigInteger, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Device(Base):
    __tablename__ = "device"

    id = Column(BigInteger, primary_key=True, index=True)
    account_id = Column(BigInteger, ForeignKey("account.id", ondelete="SET NULL"), nullable=True, index=True)
    model_id = Column(BigInteger, ForeignKey("device_model.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sn = Column(String(100), unique=True, index=True, nullable=False)
    status = Column(Enum('unbound', 'bound', 'offline', 'online', 'fatal', name='device_status'), default='unbound')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    account = relationship("Account", foreign_keys=[account_id], back_populates="devices")
    family_devices = relationship("FamilyDevice", back_populates="device", cascade="all, delete-orphan")
    network = relationship("DeviceNetwork", back_populates="device", uselist=False, passive_deletes=True)

    def __repr__(self):
        return f"<Device(id={self.id}, name='{self.name}', sn='{self.sn}', status='{self.status}')>"
