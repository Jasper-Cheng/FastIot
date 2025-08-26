from sqlalchemy.orm import Session
from app.db.models.device_data import DeviceData
from app.models.device_data import DeviceDataCreate
from typing import Optional, List
from datetime import datetime

def get_device_data(db: Session, data_id: int) -> Optional[DeviceData]:
    """根据ID获取设备数据"""
    return db.query(DeviceData).filter(DeviceData.id == data_id).first()

def get_device_data_list(db: Session, skip: int = 0, limit: int = 100) -> List[DeviceData]:
    """获取设备数据列表"""
    return db.query(DeviceData).offset(skip).limit(limit).all()

def get_device_data_by_device(db: Session, device_id: int, skip: int = 0, limit: int = 100) -> List[DeviceData]:
    """根据设备ID获取设备数据"""
    return db.query(DeviceData).filter(DeviceData.device_id == device_id).offset(skip).limit(limit).all()

def create_device_data(db: Session, device_data: DeviceDataCreate) -> DeviceData:
    """创建新的设备数据记录"""
    db_device_data = DeviceData(**device_data.dict())
    db.add(db_device_data)
    db.commit()
    db.refresh(db_device_data)
    return db_device_data

def get_latest_device_data(db: Session, device_id: int) -> Optional[DeviceData]:
    """获取设备的最新数据"""
    return db.query(DeviceData).filter(DeviceData.device_id == device_id).order_by(DeviceData.timestamp.desc()).first()

def get_device_data_by_time_range(db: Session, device_id: int, start_time: datetime, end_time: datetime) -> List[DeviceData]:
    """根据时间范围获取设备数据"""
    return db.query(DeviceData).filter(
        DeviceData.device_id == device_id,
        DeviceData.timestamp >= start_time,
        DeviceData.timestamp <= end_time
    ).order_by(DeviceData.timestamp.asc()).all()

def delete_device_data(db: Session, data_id: int) -> bool:
    """删除设备数据"""
    db_device_data = get_device_data(db, data_id)
    if not db_device_data:
        return False
    
    db.delete(db_device_data)
    db.commit()
    return True

def delete_old_device_data(db: Session, device_id: int, days: int = 30) -> int:
    """删除指定天数之前的旧数据"""
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    deleted_count = db.query(DeviceData).filter(
        DeviceData.device_id == device_id,
        DeviceData.timestamp < cutoff_date
    ).delete()
    
    db.commit()
    return deleted_count
