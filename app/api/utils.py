"""
Client API 公共工具函数

提供常用的辅助函数，减少代码重复，提高可维护性。
"""
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user_operation_log import user_operation_log
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum


# ============================================================
# Token 信息提取
# ============================================================

def extract_token_info(token_info: dict) -> Tuple[int, str, str]:
    """从 token 中提取 account_id、platform 和 role
    
    Args:
        token_info: token 信息字典
    
    Returns:
        tuple: (account_id, platform, role)
    
    Example:
        account_id, platform, role = extract_token_info(token_info)
        # 如果只需要 account_id 和 platform:
        account_id, platform, _ = extract_token_info(token_info)
    """
    account_id = token_info["account_id"]
    platform = token_info.get("platform", "app")
    role = token_info.get("role", "user")
    return account_id, platform, role


# ============================================================
# 权限检查
# ============================================================

async def check_family_member(
    db: AsyncSession,
    family_id: int,
    account_id: int,
    error_message: str = "无权访问此家庭"
) -> None:
    """检查用户是否是家庭成员
    
    Args:
        db: 数据库会话
        family_id: 家庭ID
        account_id: 账户ID
        error_message: 错误消息
    
    Raises:
        HTTPException: 如果不是家庭成员，抛出 403 错误
    """
    from app.crud.family_member import get_family_member_by_family_and_account
    
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail=error_message)


async def check_family_creator(
    db: AsyncSession,
    family_id: int,
    account_id: int,
    error_message: str = "只有家庭创建者可以执行此操作"
) -> None:
    """检查用户是否是家庭创建者
    
    Args:
        db: 数据库会话
        family_id: 家庭ID
        account_id: 账户ID
        error_message: 错误消息
    
    Raises:
        HTTPException: 如果不是创建者，抛出 403 错误
    """
    from app.crud.family_member import get_family_member_by_family_and_account
    from app.models.family_member import FamilyMemberRole
    
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member or family_member.role != FamilyMemberRole.creator:
        raise HTTPException(status_code=403, detail=error_message)


async def check_device_in_family(
    db: AsyncSession,
    device_id: int,
    family_id: int,
    error_message: str = "设备不属于此家庭"
) -> None:
    """检查设备是否属于指定家庭
    
    Args:
        db: 数据库会话
        device_id: 设备ID
        family_id: 家庭ID
        error_message: 错误消息
    
    Raises:
        HTTPException: 如果设备不属于家庭，抛出 403 错误
    """
    from app.crud.family_device import check_device_in_family as check_device
    
    if not await check_device(db, device_id, family_id):
        raise HTTPException(status_code=403, detail=error_message)


# ============================================================
# 操作日志记录
# ============================================================

async def log_operation(
    db: AsyncSession,
    account_id: int,
    operation_type: OperationTypeEnum,
    description: str,
    platform: str = "app",
    extra: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = False
) -> None:
    """记录用户操作日志
    
    Args:
        db: 数据库会话
        account_id: 账户ID
        operation_type: 操作类型
        description: 操作描述
        platform: 平台标识
        extra: 额外的日志数据
        raise_on_error: 是否在记录失败时抛出异常，默认为 False
    
    Example:
        await log_operation(
            db=db,
            account_id=account_id,
            operation_type=OperationTypeEnum.family_create,
            description=f"创建家庭: {family.name}",
            platform=platform,
            extra={"family_id": family.id}
        )
    """
    try:
        log_extra = extra or {}
        log_extra["platform"] = platform
        
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=operation_type,
                description=description,
                extra=log_extra if log_extra else None
            ),
            account_id=account_id
        )
    except Exception as e:
        print(f"记录操作日志失败: {e}")
        if raise_on_error:
            raise


async def log_operation_with_token(
    db: AsyncSession,
    token_info: dict,
    operation_type: OperationTypeEnum,
    description: str,
    extra: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = False
) -> None:
    """从 token 中提取信息并记录操作日志
    
    Args:
        db: 数据库会话
        token_info: token 信息字典
        operation_type: 操作类型
        description: 操作描述
        extra: 额外的日志数据
        raise_on_error: 是否在记录失败时抛出异常，默认为 False
    
    Example:
        await log_operation_with_token(
            db=db,
            token_info=token_info,
            operation_type=OperationTypeEnum.family_create,
            description=f"创建家庭: {family.name}",
            extra={"family_id": family.id}
        )
    """
    account_id, platform, _ = extract_token_info(token_info)
    await log_operation(
        db=db,
        account_id=account_id,
        operation_type=operation_type,
        description=description,
        platform=platform,
        extra=extra,
        raise_on_error=raise_on_error
    )


# ============================================================
# MQTT 消息发送
# ============================================================

async def send_family_notice(
    family_id: int,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None:
    """发送家庭通知消息
    
    Args:
        family_id: 家庭ID
        payload: 消息内容字典
        raise_on_error: 是否在发送失败时抛出异常，默认为 False
    
    Example:
        await send_family_notice(
            family_id=1,
            payload={
                "type": "member_added",
                "message": "有新成员加入家庭",
                "member_id": 123
            }
        )
    """
    try:
        from app.services.mqtt_service import mqtt_service
        await mqtt_service.publish_home_notice(str(family_id), payload)
    except Exception as e:
        print(f"发送家庭通知失败 (family_id={family_id}): {e}")
        if raise_on_error:
            raise


async def send_device_notice(
    device_sn: str,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None:
    """发送设备通知消息
    
    Args:
        device_sn: 设备序列号
        payload: 消息内容字典
        raise_on_error: 是否在发送失败时抛出异常，默认为 False
    
    Example:
        await send_device_notice(
            device_sn="M701001",
            payload={
                "type": "status_change",
                "message": "设备状态已更新",
                "status": "online"
            }
        )
    """
    try:
        from app.services.mqtt_service import mqtt_service
        await mqtt_service.publish_device_notice(device_sn, payload)
    except Exception as e:
        print(f"发送设备通知失败 (device_sn={device_sn}): {e}")
        if raise_on_error:
            raise


async def send_system_notice(
    platform: str,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None:
    """发送系统通知消息（按平台）
    
    Args:
        platform: 平台标识（app/web）
        payload: 消息内容字典
        raise_on_error: 是否在发送失败时抛出异常，默认为 False
    
    Example:
        await send_system_notice(
            platform="app",
            payload={
                "type": "maintenance",
                "message": "系统将在今晚进行维护",
                "start_time": "2024-01-01 00:00:00"
            }
        )
    """
    try:
        from app.services.mqtt_service import mqtt_service
        await mqtt_service.publish_system_notice(platform, payload)
    except Exception as e:
        print(f"发送系统通知失败 (platform={platform}): {e}")
        if raise_on_error:
            raise


async def send_personal_notice(
    account_id: int,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> None:
    """发送个人通知消息
    
    Args:
        account_id: 账户ID
        payload: 消息内容字典
        raise_on_error: 是否在发送失败时抛出异常，默认为 False
    
    Example:
        await send_personal_notice(
            account_id=123,
            payload={
                "type": "points_awarded",
                "message": "您获得了积分奖励",
                "points": 100
            }
        )
    """
    # TODO: 暂时屏蔽发送MQTT个人消息
    return
    
    try:
        from app.services.mqtt_service import mqtt_service
        await mqtt_service.publish_client_notice(account_id, payload)
    except Exception as e:
        print(f"发送个人通知失败 (account_id={account_id}): {e}")
        if raise_on_error:
            raise


async def send_families_notice_by_account(
    db: AsyncSession,
    account_id: int,
    payload: Dict[str, Any],
    raise_on_error: bool = False
) -> Dict[str, int]:
    """向指定账户下的所有家庭发送家庭通知消息
    
    Args:
        db: 数据库会话
        account_id: 账户ID
        payload: 消息内容字典
        raise_on_error: 是否在发送失败时抛出异常，默认为 False
    
    Returns:
        dict: 包含发送统计信息的字典，格式为 {"total": 总家庭数, "success": 成功数, "failed": 失败数}
    
    Example:
        result = await send_families_notice_by_account(
            db=db,
            account_id=123,
            payload={
                "type": "system_update",
                "message": "系统即将更新",
                "update_time": "2024-01-01 00:00:00"
            }
        )
        # result: {"total": 3, "success": 3, "failed": 0}
    """
    from app.crud.family import get_families_by_account
    
    result = {"total": 0, "success": 0, "failed": 0}
    
    try:
        # 获取该账户下的所有家庭
        families = await get_families_by_account(db, account_id)
        result["total"] = len(families)
        
        if not families:
            print(f"账户 {account_id} 下没有家庭，无需发送消息")
            return result
        
        # 遍历所有家庭，发送消息
        for family in families:
            try:
                await send_family_notice(
                    family_id=family.id,
                    payload=payload,
                    raise_on_error=False  # 单个失败不影响其他家庭
                )
                result["success"] += 1
            except Exception as e:
                result["failed"] += 1
                print(f"发送家庭通知失败 (account_id={account_id}, family_id={family.id}): {e}")
        
        print(f"✅ 已向账户 {account_id} 的 {result['total']} 个家庭发送消息: 成功 {result['success']} 个, 失败 {result['failed']} 个")
        
        # 如果所有家庭都发送失败且 raise_on_error=True，则抛出异常
        if result["failed"] > 0 and raise_on_error:
            raise Exception(f"向账户 {account_id} 的家庭发送消息时发生错误: {result['failed']} 个家庭发送失败")
            
    except Exception as e:
        print(f"获取账户 {account_id} 的家庭列表失败: {e}")
        if raise_on_error:
            raise
    
    return result

