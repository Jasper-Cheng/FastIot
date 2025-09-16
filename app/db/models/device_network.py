from sqlalchemy import Column, BigInteger, String, Integer, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class DeviceNetwork(Base):
    __tablename__ = "device_network"

    id = Column(BigInteger, primary_key=True, index=True, comment="自增主键")
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, comment="关联设备表 device 的 ID，标识具体设备实例")
    net_type = Column(String(20), nullable=False, comment="网络类型：wifi/ble/cellular/zigbee 等")
    name = Column(String(128), nullable=True, comment="网络名称：蓝牙信息：存蓝牙广播名称（如 \"Xiaomi Light 01\"）；Wi-Fi 信息：存 Wi-Fi SSID")
    ip = Column(String(64), nullable=True, comment="设备 IP 地址，仅 Wi-Fi 或蜂窝网络使用")
    mac = Column(String(64), nullable=True, comment="设备网络接口 MAC 地址：蓝牙：蓝牙唯一标识；Wi-Fi：设备 Wi-Fi 网卡 MAC")
    rssi = Column(Integer, nullable=True, comment="信号强度：蓝牙：接收信号强度；Wi-Fi：RSSI")
    connect_state = Column(Integer, default=0, comment="连接状态：0=断开, 1=连接中, 2=已连接")
    extra = Column(JSON, nullable=True, comment="扩展字段，用于存储其他网络相关信息：蓝牙：配网模式、固件版本等；Wi-Fi：网关信息、是否 2.4G/5G 等")
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="记录最后一次更新时间")

    # 关系：与设备一对一
    device = relationship("Device", back_populates="network")

    # 唯一约束：保证每个设备仅有一条网络记录（设备与网络一对一）
    __table_args__ = (
        UniqueConstraint('device_id', name='uq_device_network_device'),
    )

    def __repr__(self):
        return f"<DeviceNetwork(id={self.id}, device_id={self.device_id}, net_type='{self.net_type}', name='{self.name}', connect_state={self.connect_state})>"
