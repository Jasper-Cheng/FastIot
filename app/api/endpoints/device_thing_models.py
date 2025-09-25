from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db
from app.crud.device_thing_model import (
    get_device_thing_models,
    get_device_thing_model,
    create_device_thing_model,
    update_device_thing_model,
    delete_device_thing_model,
)
from app.models.device_thing_model import DeviceThingModelCreate, DeviceThingModelUpdate, DeviceThingModelInDB

router = APIRouter()


@router.get("/", response_model=List[DeviceThingModelInDB])
async def list_device_thing_models(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    return await get_device_thing_models(db, skip=skip, limit=limit)


@router.get("/{model_id}", response_model=DeviceThingModelInDB)
async def get_device_thing_model_detail(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await get_device_thing_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="设备物模型不存在")
    return model


@router.post("/", response_model=DeviceThingModelInDB)
async def create_device_thing_model_item(payload: DeviceThingModelCreate, db: AsyncSession = Depends(get_db)):
    """创建设备物模型
    
    示例请求体：
    {
      "name": "智能插座物模型",
      "description": "智能插座的功能定义",
      "properties": {
        "switch": {"type": "bool"},
        "current_watt": {"type": "float"},
        "voltage": {"type": "float"}
      },
      "services": ["toggle", "reset"],
      "events": ["fault", "overload"]
    }
    """
    return await create_device_thing_model(db, payload)


@router.put("/{model_id}", response_model=DeviceThingModelInDB)
async def update_device_thing_model_item(model_id: int, payload: DeviceThingModelUpdate, db: AsyncSession = Depends(get_db)):
    updated = await update_device_thing_model(db, model_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="设备物模型不存在")
    return updated


@router.delete("/{model_id}")
async def delete_device_thing_model_item(model_id: int, db: AsyncSession = Depends(get_db)):
    # 检查是否有设备型号引用该物模型
    from sqlalchemy import select
    from app.db.models.device_model import DeviceModel
    
    ref = await db.execute(select(DeviceModel.id).where(DeviceModel.thing_model_id == model_id).limit(1))
    if ref.first() is not None:
        raise HTTPException(status_code=400, detail="该设备物模型已被设备型号引用，无法删除")
    
    ok = await delete_device_thing_model(db, model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设备物模型不存在")
    return {"message": "删除成功"}
