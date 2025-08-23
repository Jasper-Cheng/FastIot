from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# 创建基础模型类
Base = declarative_base()

# 创建元数据对象
metadata = MetaData()

# 导入所有模型以确保它们被注册
from app.db.models.user import User
from app.db.models.device import Device
from app.db.models.device_data import DeviceData
from app.db.models.alert import Alert

# 导出所有模型
__all__ = ["Base", "metadata", "User", "Device", "DeviceData", "Alert"]
