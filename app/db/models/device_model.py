from sqlalchemy import Column, BigInteger, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class DeviceModel(Base):
    __tablename__ = "device_model"

    id = Column(BigInteger, primary_key=True, index=True)
    model_code = Column(String(50), nullable=False, unique=True, comment="型号代码")
    name = Column(String(100), nullable=False, comment="型号名称")
    vendor = Column(String(100), comment="厂商")
    thing_model_id = Column(BigInteger, ForeignKey("device_thing_model.id"), nullable=False, comment="物模型ID")
    properties = Column(JSON, nullable=False, comment="属性定义JSON（扩展自物模型）")
    services = Column(JSON, nullable=False, comment="服务定义JSON（扩展自物模型）")
    events = Column(JSON, nullable=False, comment="事件定义JSON（扩展自物模型）")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    # 关系
    thing_model = relationship("DeviceThingModel", back_populates="device_models")

    def __repr__(self):
        return f"<DeviceModel(id={self.id}, model_code='{self.model_code}', name='{self.name}', vendor='{self.vendor}')>"
