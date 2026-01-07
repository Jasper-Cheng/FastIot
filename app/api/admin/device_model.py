from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.api.utils import extract_token_info, log_operation_with_token
from app.crud.device_model import (
    get_device_model,
    get_device_model_by_code,
    get_device_models_with_pagination,
    get_all_device_models,
    create_device_model,
    update_device_model,
    delete_device_model,
    count_devices_by_model
)
from app.db.models.device_model import DeviceModel
from app.db.models.device_thing_model import DeviceThingModel
from app.models.user_operation_log import OperationTypeEnum

router = APIRouter()


@router.get("/device-model/list")
async def get_device_model_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    name: Optional[str] = Query(None, description="型号名称搜索"),
    code: Optional[str] = Query(None, description="型号代码搜索"),
    manufacturer: Optional[str] = Query(None, description="厂商搜索"),
    thingModelId: Optional[int] = Query(None, description="物模型ID筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取设备型号列表"""
    skip = (page - 1) * pageSize
    
    models, total = await get_device_models_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        name=name,
        code=code,
        manufacturer=manufacturer,
        thing_model_id=thingModelId,
        status=status
    )
    
    items = []
    for model in models:
        # 获取物模型名称
        thing_model_result = await db.execute(
            select(DeviceThingModel).filter(DeviceThingModel.id == model.thing_model_id)
        )
        thing_model = thing_model_result.scalar_one_or_none()
        thing_model_name = thing_model.name if thing_model else None
        
        # 统计使用该型号的设备数
        device_count = await count_devices_by_model(db, model.id)
        
        items.append({
            "id": model.id,
            "code": model.model_code,
            "name": model.name,
            "manufacturer": model.vendor,
            "thingModelId": model.thing_model_id,
            "thingModelName": thing_model_name,
            "properties": model.properties or {},
            "services": model.services or [],
            "events": model.events or [],
            "status": "active",  # 数据库中没有status字段，默认返回active
            "deviceCount": device_count,
            "createdAt": model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.get("/device-model/all")
async def get_all_device_models_list(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取所有设备型号（用于下拉选择）"""
    models = await get_all_device_models(db)
    
    items = []
    for model in models:
        # 获取物模型名称
        thing_model_result = await db.execute(
            select(DeviceThingModel).filter(DeviceThingModel.id == model.thing_model_id)
        )
        thing_model = thing_model_result.scalar_one_or_none()
        thing_model_name = thing_model.name if thing_model else None
        
        items.append({
            "id": model.id,
            "code": model.model_code,
            "name": model.name,
            "manufacturer": model.vendor,
            "thingModelId": model.thing_model_id,
            "thingModelName": thing_model_name,
            "properties": model.properties or {},
            "services": model.services or [],
            "events": model.events or [],
            "status": "active",
            "createdAt": model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else None
        })
    
    return items


@router.post("/device-model")
async def create_device_model_info(
    model_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建设备型号"""
    # 验证必填字段
    if not model_data.get("code"):
        raise HTTPException(status_code=400, detail="型号代码不能为空")
    if not model_data.get("name"):
        raise HTTPException(status_code=400, detail="型号名称不能为空")
    if not model_data.get("thingModelId"):
        raise HTTPException(status_code=400, detail="物模型ID不能为空")
    
    # 验证型号代码唯一性
    existing_model = await get_device_model_by_code(db, model_data["code"])
    if existing_model:
        raise HTTPException(status_code=400, detail="型号代码已存在")
    
    # 验证物模型是否存在
    from app.crud.thing_model import get_thing_model
    thing_model = await get_thing_model(db, model_data["thingModelId"])
    if not thing_model:
        raise HTTPException(status_code=404, detail="物模型不存在")
    
    model = await create_device_model(db, model_data)
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_model_create,
        description=f"创建设备型号：{model.name}（代码: {model.model_code}）",
        extra={
            "model_id": model.id,
            "model_code": model.model_code,
            "model_name": model.name,
            "thing_model_id": model.thing_model_id,
            "thing_model_name": thing_model.name
        }
    )
    
    return {
        "id": model.id,
        "code": model.model_code,
        "name": model.name,
        "manufacturer": model.vendor,
        "thingModelId": model.thing_model_id,
        "thingModelName": thing_model.name,
        "properties": model.properties or {},
        "services": model.services or [],
        "events": model.events or [],
        "status": "active",
        "createdAt": model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else None
    }


@router.put("/device-model/{id}")
async def update_device_model_info(
    id: int,
    model_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新设备型号"""
    # 验证设备型号是否存在
    model = await get_device_model(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    # 如果更新了code，验证唯一性
    if "code" in model_data and model_data["code"] != model.model_code:
        existing_model = await get_device_model_by_code(db, model_data["code"])
        if existing_model:
            raise HTTPException(status_code=400, detail="型号代码已存在")
    
    # 如果更新了thingModelId，验证物模型是否存在
    if "thingModelId" in model_data:
        from app.crud.thing_model import get_thing_model
        thing_model = await get_thing_model(db, model_data["thingModelId"])
        if not thing_model:
            raise HTTPException(status_code=404, detail="物模型不存在")
    
    # 保存更新前的信息用于日志
    old_name = model.name
    old_code = model.model_code
    
    updated_model = await update_device_model(db, id, model_data)
    if not updated_model:
        raise HTTPException(status_code=500, detail="更新失败")
    
    # 获取物模型名称
    thing_model_result = await db.execute(
        select(DeviceThingModel).filter(DeviceThingModel.id == updated_model.thing_model_id)
    )
    thing_model = thing_model_result.scalar_one_or_none()
    
    # 记录操作日志
    changes = []
    if "name" in model_data and old_name != updated_model.name:
        changes.append(f"名称: {old_name} -> {updated_model.name}")
    if "code" in model_data and old_code != updated_model.model_code:
        changes.append(f"代码: {old_code} -> {updated_model.model_code}")
    if "thingModelId" in model_data:
        changes.append("更新物模型")
    
    log_description = f"更新设备型号：{updated_model.name}" + (f" - {', '.join(changes)}" if changes else "")
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_model_update,
        description=log_description,
        extra={
            "model_id": id,
            "old_name": old_name,
            "new_name": updated_model.name,
            "old_code": old_code,
            "new_code": updated_model.model_code,
            "changes": changes
        }
    )
    
    return {
        "id": updated_model.id,
        "code": updated_model.model_code,
        "name": updated_model.name,
        "manufacturer": updated_model.vendor,
        "thingModelId": updated_model.thing_model_id,
        "thingModelName": thing_model.name if thing_model else None,
        "properties": updated_model.properties or {},
        "services": updated_model.services or [],
        "events": updated_model.events or [],
        "status": "active"
    }


@router.delete("/device-model/{id}")
async def delete_device_model_info(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除设备型号"""
    # 验证设备型号是否存在
    model = await get_device_model(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    # 保存型号信息用于日志
    model_name = model.name
    model_code = model.model_code
    
    try:
        success = await delete_device_model(db, id)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_model_delete,
        description=f"删除设备型号：{model_name}（代码: {model_code}）",
        extra={
            "model_id": id,
            "model_name": model_name,
            "model_code": model_code
        }
    )
    
    return {}

