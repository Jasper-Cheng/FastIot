from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import select

from app.db.session import get_db
from app.crud.device_model import (
    get_device_models,
    get_device_models_by_vendor,
    get_device_model,
    create_device_model,
    update_device_model,
    delete_device_model,
)
from app.crud.device_thing_model import get_device_thing_model
from app.models.device_model import (
    DeviceModelCreate,
    DeviceModelUpdate,
    DeviceModelInDB,
)
from app.db.models.device import Device
from app.db.models.device_model import DeviceModel

router = APIRouter()


@router.get("/", response_model=List[DeviceModelInDB])
async def list_device_models(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    vendor: Optional[str] = Query(None, description="按厂商筛选"),
):
    if vendor:
        return await get_device_models_by_vendor(db, vendor=vendor, skip=skip, limit=limit)
    return await get_device_models(db, skip=skip, limit=limit)


@router.get("/{model_id}", response_model=DeviceModelInDB)
async def get_device_model_detail(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await get_device_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    return model


@router.post("/", response_model=DeviceModelInDB)
async def create_device_model_item(payload: DeviceModelCreate, db: AsyncSession = Depends(get_db)):
    """创建设备型号
    
    示例请求体：
    {
      "model_code": "SN01",
      "name": "插座1000W",
      "vendor": "SmartHome Inc",
      "thing_model_id": 1,
      "properties": {
        "power": {"type": "boolean", "unit": "on/off", "default": false, "readable": true, "writable": true},
        "voltage": {"type": "float", "unit": "V", "min": 0, "max": 250, "precision": 1, "readable": true, "writable": false}
      },
      "services": ["power_on", "power_off", "set_voltage", "reset"],
      "events": ["power_changed", "voltage_alert", "device_fault"]
    }
    """
    # 验证设备物模型存在
    thing_model = await get_device_thing_model(db, payload.thing_model_id)
    if not thing_model:
        raise HTTPException(status_code=400, detail="设备物模型不存在")
    
    # 验证型号代码唯一性
    existing_model = await db.execute(select(DeviceModel).filter(DeviceModel.model_code == payload.model_code))
    if existing_model.first() is not None:
        raise HTTPException(status_code=400, detail="型号代码已存在")
    
    return await create_device_model(db, payload)


@router.put("/{model_id}", response_model=DeviceModelInDB)
async def update_device_model_item(model_id: int, payload: DeviceModelUpdate, db: AsyncSession = Depends(get_db)):
    """更新设备型号
    
    示例请求体：
    {
      "model_code": "SN01",
      "name": "插座1000W",
      "vendor": "SmartHome Inc",
      "thing_model_id": 1,
      "properties": {"power": {"type": "boolean", "unit": "on/off", "readable": true, "writable": true}},
      "services": ["power_on", "power_off"],
      "events": ["power_changed", "device_fault"]
    }
    """
    # 如果提供了thing_model_id，验证设备物模型存在
    if payload.thing_model_id is not None:
        thing_model = await get_device_thing_model(db, payload.thing_model_id)
        if not thing_model:
            raise HTTPException(status_code=400, detail="设备物模型不存在")
    
    # 如果提供了model_code，验证唯一性（排除当前记录）
    if payload.model_code is not None:
        existing_model = await db.execute(
            select(DeviceModel).filter(
                DeviceModel.model_code == payload.model_code,
                DeviceModel.id != model_id
            )
        )
        if existing_model.first() is not None:
            raise HTTPException(status_code=400, detail="型号代码已存在")
    
    updated = await update_device_model(db, model_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    return updated


@router.delete("/{model_id}")
async def delete_device_model_item(model_id: int, db: AsyncSession = Depends(get_db)):
    # 若存在设备引用该型号，禁止删除，返回 400
    ref = await db.execute(select(Device.id).where(Device.model_id == model_id).limit(1))
    if ref.first() is not None:
        raise HTTPException(status_code=400, detail="该设备型号已被设备引用，无法删除")
    ok = await delete_device_model(db, model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    return {"message": "删除成功"}