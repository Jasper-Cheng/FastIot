from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.device import (
    get_device,
    get_device_by_sn,
    get_devices_with_pagination,
    create_device,
    update_device,
    delete_device
)
from app.crud.family_device import get_device_families
from app.db.models.device import Device
from app.db.models.device_model import DeviceModel
from app.db.models.account import Account
from app.db.models.device_network import DeviceNetwork
from app.db.models.family_device import FamilyDevice
from app.models.device import DeviceCreate, DeviceUpdate, DeviceStatus

router = APIRouter()


@router.post("/device")
async def create_device_info(
    device_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """设备入库：创建设备记录"""
    # 验证必填字段
    if not device_data.get("name"):
        raise HTTPException(status_code=400, detail="设备名称不能为空")
    if not device_data.get("sn"):
        raise HTTPException(status_code=400, detail="设备序列号不能为空")
    if not device_data.get("modelId"):
        raise HTTPException(status_code=400, detail="设备型号ID不能为空")
    
    # 验证设备序列号唯一性
    existing_device = await get_device_by_sn(db, device_data["sn"])
    if existing_device:
        raise HTTPException(status_code=400, detail="设备序列号已存在")
    
    # 验证设备型号是否存在
    model_result = await db.execute(
        select(DeviceModel).filter(DeviceModel.id == device_data["modelId"])
    )
    model = model_result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    # 构建创建设备数据（入库时 account_id 固定为 null，status 固定为 unbound）
    device_create = DeviceCreate(
        name=device_data["name"],
        sn=device_data["sn"],
        model_id=device_data["modelId"],
        account_id=None,  # 入库时默认为 null（未绑定）
        status=DeviceStatus.unbound  # 入库时默认为 unbound
    )
    
    # 创建设备
    new_device = await create_device(db, device_create)
    
    # 立即保存设备属性到局部变量，避免懒加载问题
    device_id = new_device.id
    device_name = new_device.name
    device_sn = new_device.sn
    device_model_id = new_device.model_id
    device_status = new_device.status
    device_created_at = new_device.created_at
    
    # 获取设备型号名称
    model_name = model.name if model else None
    
    # 记录操作日志
    try:
        from app.crud.user_operation_log import user_operation_log
        from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
        
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_create,
                description=f"设备入库：{device_name}（SN: {device_sn}）",
                extra={
                    "device_id": device_id,
                    "device_name": device_name,
                    "device_sn": device_sn,
                    "model_id": device_model_id,
                    "model_name": model_name,
                    "status": device_status
                }
            ),
            account_id=token_info.get("account_id")
        )
    except Exception as e:
        # 记录操作失败不影响设备入库流程
        print(f"记录设备入库操作日志失败: {e}")
    
    return {
        "id": device_id,
        "name": device_name,
        "sn": device_sn,
        "modelId": device_model_id,
        "modelName": model_name,
        "accountId": None,
        "accountName": None,
        "status": device_status,
        "createdAt": device_created_at.strftime("%Y-%m-%d %H:%M:%S") if device_created_at else None
    }


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
    
    # 获取网络信息（如果有）- 使用显式查询避免懒加载问题
    network_info = None
    network_result = await db.execute(
        select(DeviceNetwork).filter(DeviceNetwork.device_id == device.id)
    )
    network = network_result.scalar_one_or_none()
    if network:
        network_info = {
            "netType": network.net_type,
            "name": network.name,
            "ip": network.ip,
            "mac": network.mac,
            "rssi": network.rssi,
            "connectState": network.connect_state,
            "lastUpdate": network.last_update.strftime("%Y-%m-%d %H:%M:%S") if network.last_update else None
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
        # accountId 为 null 表示解绑用户，同时更新状态为 unbound
        account_id_value = device_data["accountId"]
        update_data.account_id = account_id_value
        from app.models.device import DeviceStatus
        # 当 accountId 为 null 时，更新 status 为 unbound，并移除所有家庭关联
        if account_id_value is None:
            update_data.status = DeviceStatus.unbound
            # 同步移除设备与所有家庭的关联
            from app.crud.family_device import delete_all_family_devices_by_device
            await delete_all_family_devices_by_device(db, id)
        else:
            # 当 accountId 不为 null 时（绑定设备），更新 status 为 bound
            # 如果设备之前未绑定（account_id 为 None），绑定后设置为 bound
            if device.account_id is None:
                update_data.status = DeviceStatus.bound
    
    # 保存更新前的设备信息用于日志
    old_name = device.name
    old_account_id = device.account_id
    old_status = device.status
    
    updated_device = await update_device(db, id, update_data)
    if not updated_device:
        raise HTTPException(status_code=500, detail="更新失败")
    
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
    
    # 记录操作日志
    try:
        from app.crud.user_operation_log import user_operation_log
        from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
        
        # 构建操作描述
        changes = []
        if "name" in device_data and old_name != updated_device.name:
            changes.append(f"名称: {old_name} -> {updated_device.name}")
        if "accountId" in device_data:
            if old_account_id != updated_device.account_id:
                if updated_device.account_id is None:
                    changes.append("解绑用户")
                else:
                    changes.append(f"绑定用户: {account_name or updated_device.account_id}")
        if "modelId" in device_data:
            changes.append("更新型号")
        if changes:
            description = f"更新设备：{updated_device.name}（SN: {updated_device.sn}）- {', '.join(changes)}"
        else:
            description = f"更新设备：{updated_device.name}（SN: {updated_device.sn}）"
        
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_update,
                description=description,
                extra={
                    "device_id": updated_device.id,
                    "device_name": updated_device.name,
                    "device_sn": updated_device.sn,
                    "old_name": old_name,
                    "new_name": updated_device.name,
                    "old_account_id": old_account_id,
                    "new_account_id": updated_device.account_id,
                    "old_status": old_status,
                    "new_status": updated_device.status,
                    "model_id": updated_device.model_id
                }
            ),
            account_id=token_info.get("account_id")
        )
    except Exception as e:
        # 记录操作失败不影响更新流程
        print(f"记录设备更新操作日志失败: {e}")
    
    return {
        "id": updated_device.id,
        "name": updated_device.name,
        "modelId": updated_device.model_id,
        "accountId": updated_device.account_id,
        "accountName": account_name,
        "status": updated_device.status
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
    
    # 保存设备信息用于日志
    device_name = device.name
    device_sn = device.sn
    device_model_id = device.model_id
    
    success = await delete_device(db, id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    # 记录操作日志
    try:
        from app.crud.user_operation_log import user_operation_log
        from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
        
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_delete,
                description=f"删除设备：{device_name}（SN: {device_sn}）",
                extra={
                    "device_id": id,
                    "device_name": device_name,
                    "device_sn": device_sn,
                    "model_id": device_model_id,
                    "status": device.status
                }
            ),
            account_id=token_info.get("account_id")
        )
    except Exception as e:
        # 记录操作失败不影响删除流程
        print(f"记录设备删除操作日志失败: {e}")
    
    return {}

