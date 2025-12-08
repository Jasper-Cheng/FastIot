from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.crud.device_message import (
    get_account_device_messages,
    update_device_message_status,
    mark_all_account_device_messages_read,
    get_device_message,
)
from app.crud.device import get_device
from app.models.device_message import (
    DeviceMessageInDB,
    DeviceMessageStatus,
    DeviceMessageLevel,
)
from app.api.dependencies import get_current_token, get_family_clients
from app.db.session import get_db
from app.services.websocket_tool import websocket_tool
router = APIRouter()


@router.get("/", response_model=List[DeviceMessageInDB])
async def list_device_messages(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    level: Optional[List[str]] = Query(None, description="按消息级别筛选，可传入多个值 (low, normal, error, fatal)"),
    status: Optional[str] = Query(None, description="按消息状态极筛选 (new, read)"),
    family_id: Optional[int] = Query(None, description="家庭ID，如果提供则返回该家庭中所有设备的消息；如果不提供则返回个人所有设备的消息")
):
    """获取设备消息列表
    
    - 如果有 family_id：返回该家庭中所有设备的消息
    - 如果没有 family_id：返回个人所有设备的消息
    
    支持按级别、状态筛选
    """
    # 验证 level 参数
    if level is not None:
        valid_levels = [l.value for l in DeviceMessageLevel]
        invalid_levels = [l for l in level if l not in valid_levels]
        if invalid_levels:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息级别: {', '.join(invalid_levels)}。有效值: {', '.join(valid_levels)}"
            )
    
    # 验证 status 参数
    if status is not None:
        try:
            DeviceMessageStatus(status)
        except ValueError:
            valid_statuses = [s.value for s in DeviceMessageStatus]
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息状态 '{status}'。有效值: {', '.join(valid_statuses)}"
            )
    
    # 使用token中的account_id
    account_id = token_info["account_id"]
    
    # 如果提供了 family_id，验证是否是家庭成员
    if family_id:
        from app.crud.family_member import get_family_member_by_family_and_account
        family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
        if not family_member:
            raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    # 在数据库查询中应用过滤条件和分页
    alerts = await get_account_device_messages(
        db, 
        account_id, 
        skip=skip,
        limit=limit,
        level=level,
        status=status,
        family_id=family_id
    )
    
    return alerts


@router.patch("/{message_id}/make-read", response_model=DeviceMessageInDB)
async def make_device_message_read(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    family_clients: list[str] = Depends(get_family_clients)
):
    """标记设备消息为已读状态"""
    account_id = token_info["account_id"]
    
    # 获取消息记录
    message = await get_device_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    
    # 更新消息状态为已读
    updated = await update_device_message_status(db, message_id, DeviceMessageStatus.read)
    if not updated:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    
    # 获取消息关联的设备（用于websocket通知）
    device = await get_device(db, message.device_id)
    device_name = device.name if device else None
    device_id = device.id if device else message.device_id
    
    # 发送websocket消息通知设备消息已读
    try:
        role = token_info.get("role")
        if account_id is not None:
            await websocket_tool.send_family_message(
                message_type="device.message.read",
                data={
                    "senderId": account_id,
                    "senderRole": role,
                    "title": "设备消息已读",
                    "message": f"设备 {device_name or device_id} 的消息已标记为已读",
                    "level": "normal",
                    "deviceId": device_id,
                    "deviceName": device_name,
                    "messageId": message_id
                },
                family_clients=family_clients
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送设备消息已读通知失败: {e}")
    
    return updated


@router.patch("/mark-all-read")
async def mark_all_device_messages_read(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    family_clients: list[str] = Depends(get_family_clients),
    family_id: Optional[int] = Query(None, description="家庭ID，如果提供则标记该家庭中所有设备的消息为已读；如果不提供则标记个人所有设备的消息为已读")
):
    """标记设备消息为已读
    
    - 如果有 family_id：标记该家庭中所有设备的消息为已读
    - 如果没有 family_id：标记个人所有设备的消息为已读
    """
    # 使用token中的account_id
    account_id = token_info["account_id"]
    
    # 如果提供了 family_id，验证是否是家庭成员
    if family_id:
        from app.crud.family_member import get_family_member_by_family_and_account
        family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
        if not family_member:
            raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    # 更新设备消息状态为已读
    count = await mark_all_account_device_messages_read(db, account_id, family_id=family_id)
    
    # 发送websocket消息通知所有设备消息已读
    try:
        role = token_info.get("role")
        if account_id is not None:
            await websocket_tool.send_family_message(
                message_type="device.message.mark_all_read",
                data={
                    "senderId": account_id,
                    "senderRole": role,
                    "title": "所有设备消息已读",
                    "message": f"{count} 条设备消息已标记为已读",
                    "level": "normal",
                    "count": count
                },
                family_clients=family_clients
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送所有设备消息已读通知失败: {e}")
    
    if family_id:
        return {"message": f"家庭 {family_id} 的 {count} 条设备消息已标记为已读"}
    else:
        return {"message": f"账号 {account_id} 的 {count} 条设备消息已标记为已读"}
