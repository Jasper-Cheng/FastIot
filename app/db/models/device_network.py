from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class DeviceNetwork(Base):
    __tablename__ = "device_network"

    id = Column(BigInteger, primary_key=True, index=True, comment="自增主键")
    sn = Column(String(100), ForeignKey("device.sn", ondelete="CASCADE"), nullable=False, comment="关联设备表 device 的序列号，标识具体设备实例")
    ip = Column(String(64), nullable=True, comment="设备 IP 地址")
    mac = Column(String(64), nullable=True, comment="设备 MAC 地址")
    ble_name = Column(String(128), nullable=True, comment="蓝牙名称")
    wifi_name = Column(String(128), nullable=True, comment="Wi-Fi 名称（SSID）")
    wifi_password = Column(String(255), nullable=True, comment="Wi-Fi 密码")
    mqtt_broker = Column(String(255), nullable=True, comment="MQTT 代理服务器地址")
    mqtt_port = Column(Integer, nullable=True, comment="MQTT 端口号")
    firmware = Column(String(128), nullable=True, comment="固件版本")
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="记录最后一次更新时间")

    # 关系：与设备一对一
    device = relationship("Device", primaryjoin="DeviceNetwork.sn == Device.sn", back_populates="network")

    # 唯一约束：保证每个设备仅有一条网络记录（设备与网络一对一）
    __table_args__ = (
        UniqueConstraint('sn', name='uq_device_network_device'),
    )

    def __repr__(self):
        return f"<DeviceNetwork(id={self.id}, sn='{self.sn}', ip='{self.ip}', mac='{self.mac}', firmware='{self.firmware}')>"
