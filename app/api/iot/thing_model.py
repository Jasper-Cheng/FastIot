from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.thing_model import (
    get_thing_model,
    get_thing_models_with_pagination,
    create_thing_model,
    update_thing_model,
    delete_thing_model,
    count_devices_by_thing_model
)

router = APIRouter()


@router.get("/thing-model/list")
async def get_thing_model_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    name: Optional[str] = Query(None, description="物模型名称搜索"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取物模型列表"""
    skip = (page - 1) * pageSize
    
    models, total = await get_thing_models_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        name=name
    )
    
    items = []
    for model in models:
        # 统计使用该物模型的设备数
        device_count = await count_devices_by_thing_model(db, model.id)
        
        items.append({
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "properties": model.properties or {},
            "services": model.services or [],
            "events": model.events or [],
            "deviceCount": device_count,
            "createdAt": model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.get("/thing-model/{id}")
async def get_thing_model_detail(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取物模型详情"""
    model = await get_thing_model(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="物模型不存在")
    
    # 统计使用该物模型的设备数
    device_count = await count_devices_by_thing_model(db, model.id)
    
    return {
        "id": model.id,
        "name": model.name,
        "description": model.description,
        "properties": model.properties or {},
        "services": model.services or [],
        "events": model.events or [],
        "deviceCount": device_count,
        "createdAt": model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else None
    }


@router.post("/thing-model")
async def create_thing_model_info(
    model_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建物模型"""
    # 验证必填字段
    if not model_data.get("name"):
        raise HTTPException(status_code=400, detail="物模型名称不能为空")
    
    model = await create_thing_model(db, model_data)
    
    return {
        "id": model.id,
        "name": model.name,
        "description": model.description,
        "properties": model.properties or {},
        "services": model.services or [],
        "events": model.events or [],
        "createdAt": model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else None
    }


@router.put("/thing-model/{id}")
async def update_thing_model_info(
    id: int,
    model_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新物模型"""
    # 验证物模型是否存在
    model = await get_thing_model(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="物模型不存在")
    
    updated_model = await update_thing_model(db, id, model_data)
    if not updated_model:
        raise HTTPException(status_code=500, detail="更新失败")
    
    return {
        "id": updated_model.id,
        "name": updated_model.name,
        "description": updated_model.description,
        "properties": updated_model.properties or {},
        "services": updated_model.services or [],
        "events": updated_model.events or []
    }


@router.delete("/thing-model/{id}")
async def delete_thing_model_info(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除物模型"""
    # 验证物模型是否存在
    model = await get_thing_model(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="物模型不存在")
    
    try:
        success = await delete_thing_model(db, id)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {}


@router.post("/thing-model/{id}/publish")
async def publish_thing_model(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """发布物模型"""
    # 验证物模型是否存在
    model = await get_thing_model(db, id)
    if not model:
        raise HTTPException(status_code=404, detail="物模型不存在")
    
    # 这里可以添加发布逻辑，比如更新状态、推送给相关设备等
    # 目前只是返回成功
    return {}

