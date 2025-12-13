from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.device import (
    get_device,
    get_devices_with_pagination,
    update_device,
    delete_device
)
from app.crud.family_device import get_device_families
from app.db.models.device import Device
from app.db.models.device_model import DeviceModel
from app.db.models.account import Account
from app.db.models.family_device import FamilyDevice
from app.models.device import DeviceUpdate

router = APIRouter()


@router.get("/device/list")
async def get_device_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    sn: Optional[str] = Query(None, description="设备序列号搜索（模糊匹配）"),
    name: Optional[str] = Query(None, description="设备名称搜索（模糊匹配）"),
    modelId: Optional[int] = Query(None, description="设备型号ID筛选"),
    status: Optional[str] = Query(None, description="设备状态筛选"),
    accountId: Optional[int] = Query(None, description="账号ID筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取设备列表（支持分页和搜索）"""
    skip = (page - 1) * pageSize
    
    devices, total = await get_devices_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        sn=sn,
        name=name,
        model_id=modelId,
        status=status,
        account_id=accountId
    )
    
    items = []
    for device in devices:
        # 获取账号信息
        account_name = None
        if device.account_id:
            account_result = await db.execute(
                select(Account).filter(Account.id == device.account_id)
            )
            account = account_result.scalar_one_or_none()
            if account:
                account_name = account.nickname or account.phone
        
        # 获取设备型号信息
        model_result = await db.execute(
            select(DeviceModel).filter(DeviceModel.id == device.model_id)
        )
        model = model_result.scalar_one_or_none()
        model_name = model.name if model else None
        
        # 获取物模型ID（从设备型号中获取）
        thing_model_id = model.thing_model_id if model else None
        
        # 获取设备所属的家庭
        families = await get_device_families(db, device.id, skip=0, limit=100)
        family_ids = [f.id for f in families]
        family_names = [f.name for f in families]
        
        items.append({
            "id": device.id,
            "accountId": device.account_id,
            "accountName": account_name,
            "modelId": device.model_id,
            "modelName": model_name,
            "thingModelId": thing_model_id,
            "name": device.name,
            "sn": device.sn,
            "status": device.status,
            "familyIds": family_ids,
            "familyNames": family_names,
            "createdAt": device.created_at.strftime("%Y-%m-%d %H:%M:%S") if device.created_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.get("/device/{id}")
async def get_device_detail(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取设备详情"""
    device = await get_device(db, id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 获取设备型号信息
    model_result = await db.execute(
        select(DeviceModel).filter(DeviceModel.id == device.model_id)
    )
    model = model_result.scalar_one_or_none()
    
    # 获取账号信息
    account_name = None
    if device.account_id:
        account_result = await db.execute(
            select(Account).filter(Account.id == device.account_id)
        )
        account = account_result.scalar_one_or_none()
        if account:
            account_name = account.nickname or account.phone
    
    # 获取网络信息（如果有）
    network_info = None
    if device.network:
        network_info = {
            "netType": device.network.net_type,
            "name": device.network.name,
            "ip": device.network.ip,
            "mac": device.network.mac,
            "rssi": device.network.rssi,
            "connectState": device.network.connect_state,
            "lastUpdate": device.network.last_update.strftime("%Y-%m-%d %H:%M:%S") if device.network.last_update else None
        }
    
    # 获取设备所属的家庭
    families = await get_device_families(db, device.id, skip=0, limit=100)
    family_ids = [f.id for f in families]
    
    # 获取物模型属性（从设备型号中获取）
    properties = {}
    if model and model.properties:
        properties = model.properties
    
    result = {
        "id": device.id,
        "sn": device.sn,
        "name": device.name,
        "modelId": device.model_id,
        "modelName": model.name if model else None,
        "thingModelId": model.thing_model_id if model else None,
        "status": device.status,
        "createdAt": device.created_at.strftime("%Y-%m-%d %H:%M:%S") if device.created_at else None,
        "properties": properties
    }
    
    if network_info:
        result["lastOnlineTime"] = network_info["lastUpdate"]
        result["mac"] = network_info["mac"]
        result["firmware"] = None  # 如果数据库中有固件版本字段，可以添加
    
    return result


@router.put("/device/{id}")
async def update_device_info(
    id: int,
    device_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新设备信息"""
    # 验证设备是否存在
    device = await get_device(db, id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 构建更新数据
    update_data = DeviceUpdate()
    if "name" in device_data:
        update_data.name = device_data["name"]
    if "modelId" in device_data:
        update_data.model_id = device_data["modelId"]
    if "accountId" in device_data:
        # accountId 为 null 表示解绑用户
        update_data.account_id = device_data["accountId"]
    
    updated_device = await update_device(db, id, update_data)
    if not updated_device:
        raise HTTPException(status_code=500, detail="更新失败")
    
    # 更新家庭关联
    if "familyIds" in device_data:
        family_ids = device_data["familyIds"]
        
        # 获取当前的家庭关联
        current_families = await get_device_families(db, id, skip=0, limit=100)
        current_family_ids = {f.id for f in current_families}
        new_family_ids = set(family_ids)
        
        # 需要添加的家庭
        to_add = new_family_ids - current_family_ids
        # 需要删除的家庭
        to_remove = current_family_ids - new_family_ids
        
        from app.crud.family_device import create_family_device, delete_family_device
        
        # 添加新的家庭关联
        for family_id in to_add:
            await create_family_device(db, family_id, id)
        
        # 删除旧的家庭关联
        for family_id in to_remove:
            await delete_family_device(db, family_id, id)
        
        await db.commit()
    
    # 获取更新后的设备信息
    updated_device = await get_device(db, id)
    
    # 获取账号名称
    account_name = None
    if updated_device.account_id:
        account_result = await db.execute(
            select(Account).filter(Account.id == updated_device.account_id)
        )
        account = account_result.scalar_one_or_none()
        if account:
            account_name = account.nickname or account.phone
    
    # 获取家庭ID列表
    families = await get_device_families(db, id, skip=0, limit=100)
    family_ids = [f.id for f in families]
    
    return {
        "id": updated_device.id,
        "name": updated_device.name,
        "modelId": updated_device.model_id,
        "accountId": updated_device.account_id,
        "accountName": account_name,
        "familyIds": family_ids
    }


@router.delete("/device/{id}")
async def delete_device_info(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除设备"""
    # 验证设备是否存在
    device = await get_device(db, id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    success = await delete_device(db, id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {}

