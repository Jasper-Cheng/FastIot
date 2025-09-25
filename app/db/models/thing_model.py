from sqlalchemy import Column, BigInteger, String, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class ThingModel(Base):
    __tablename__ = "device_thing_model"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="物模型名称")
    description = Column(String(500), comment="物模型描述")
    properties = Column(JSON, nullable=False, comment="属性定义JSON")
    services = Column(JSON, nullable=False, comment="服务定义JSON")
    events = Column(JSON, nullable=False, comment="事件定义JSON")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    # 关系
    device_models = relationship("DeviceModel", back_populates="thing_model")

    def __repr__(self):
        return f"<ThingModel(id={self.id}, name='{self.name}')>"
