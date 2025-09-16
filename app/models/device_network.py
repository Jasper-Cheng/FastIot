from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class NetworkType(str, Enum):
    wifi = "wifi"
    ble = "ble"
    cellular = "cellular"
    zigbee = "zigbee"
    ethernet = "ethernet"
    lora = "lora"

class ConnectState(int, Enum):
    disconnected = 0  # 断开
    connecting = 1    # 连接中
    connected = 2     # 已连接

class DeviceNetworkBase(BaseModel):
    device_id: int = Field(..., description="关联设备表 device 的 ID")
    net_type: NetworkType = Field(..., description="网络类型：wifi/ble/cellular/zigbee 等")
    name: Optional[str] = Field(None, max_length=128, description="网络名称：蓝牙信息：存蓝牙广播名称；Wi-Fi 信息：存 Wi-Fi SSID")
    ip: Optional[str] = Field(None, max_length=64, description="设备 IP 地址，仅 Wi-Fi 或蜂窝网络使用")
    mac: Optional[str] = Field(None, max_length=64, description="设备网络接口 MAC 地址")
    rssi: Optional[int] = Field(None, description="信号强度：蓝牙：接收信号强度；Wi-Fi：RSSI")
    connect_state: ConnectState = Field(ConnectState.disconnected, description="连接状态：0=断开, 1=连接中, 2=已连接")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展字段，用于存储其他网络相关信息")

class DeviceNetworkCreate(DeviceNetworkBase):
    pass

class DeviceNetworkUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    ip: Optional[str] = Field(None, max_length=64)
    mac: Optional[str] = Field(None, max_length=64)
    rssi: Optional[int] = None
    connect_state: Optional[ConnectState] = None
    extra: Optional[Dict[str, Any]] = None

class DeviceNetworkInDB(DeviceNetworkBase):
    id: int
    last_update: datetime

    class Config:
        from_attributes = True

class DeviceNetwork(DeviceNetworkInDB):
    pass
