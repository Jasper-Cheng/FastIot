from sqlalchemy.orm import Session
from app.db.models.device import Device
from app.models.device import DeviceCreate, DeviceUpdate
from typing import Optional, List

def get_device(db: Session, device_id: int) -> Optional[Device]:
    """根据ID获取设备"""
    return db.query(Device).filter(Device.id == device_id).first()

def get_devices(db: Session, skip: int = 0, limit: int = 100) -> List[Device]:
    """获取设备列表"""
    return db.query(Device).offset(skip).limit(limit).all()

def get_device_by_serial(db: Session, serial_number: str) -> Optional[Device]:
    """根据序列号获取设备"""
    return db.query(Device).filter(Device.serial_number == serial_number).first()

def create_device(db: Session, device: DeviceCreate) -> Device:
    """创建新设备"""
    db_device = Device(**device.dict())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

def update_device(db: Session, device_id: int, device: DeviceUpdate) -> Optional[Device]:
    """更新设备信息"""
    db_device = get_device(db, device_id)
    if not db_device:
        return None
    
    update_data = device.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_device, field, value)
    
    db.commit()
    db.refresh(db_device)
    return db_device

def delete_device(db: Session, device_id: int) -> bool:
    """删除设备"""
    db_device = get_device(db, device_id)
    if not db_device:
        return False
    
    db.delete(db_device)
    db.commit()
    return True

def get_devices_by_owner(db: Session, owner_id: int, skip: int = 0, limit: int = 100) -> List[Device]:
    """根据所有者ID获取设备列表"""
    return db.query(Device).filter(Device.owner_id == owner_id).offset(skip).limit(limit).all()
