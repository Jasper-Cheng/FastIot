from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, func

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.api.utils import extract_token_info, log_operation_with_token
from app.crud.family import (
    get_family,
    get_families_with_pagination,
    create_family,
    update_family,
    delete_family
)
from app.crud.family_member import (
    get_family_members_by_family,
    create_family_member,
    remove_family_member_by_family_and_account
)
from app.crud.family_device import get_family_devices, get_device_families
from app.models.family import FamilyCreate, FamilyUpdate
from app.models.family_member import FamilyMemberCreate
from app.db.models.family import Family
from app.db.models.family_member import FamilyMember
from app.db.models.account import Account
from app.db.models.device import Device
import secrets
import string

router = APIRouter()


def generate_invite_code() -> str:
    """生成邀请码（格式：HOME + 数字）"""
    # 生成 HOME + 6位数字
    number_part = ''.join(secrets.choice(string.digits) for _ in range(6))
    return f"HOME{number_part}"


@router.get("/family/list")
async def get_family_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    name: Optional[str] = Query(None, description="家庭名称搜索（模糊匹配）"),
    inviteCode: Optional[str] = Query(None, description="邀请码搜索（模糊匹配）"),
    memberId: Optional[int] = Query(None, description="成员ID搜索（查找包含该成员的家庭）"),
    deviceId: Optional[int] = Query(None, description="设备ID搜索（查找包含该设备的家庭）"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取家庭列表"""
    skip = (page - 1) * pageSize
    
    families, total = await get_families_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        name=name,
        invite_code=inviteCode,
        member_id=memberId,
        device_id=deviceId
    )
    
    items = []
    for family in families:
        # 统计成员数
        member_count_result = await db.execute(
            select(func.count(FamilyMember.id)).filter(FamilyMember.family_id == family.id)
        )
        member_count = member_count_result.scalar() or 0
        
        # 获取成员ID列表和名字列表
        members_result = await db.execute(
            select(FamilyMember.account_id).filter(FamilyMember.family_id == family.id)
        )
        member_ids = [row[0] for row in members_result.all()]
        
        # 获取成员名字列表
        member_names = []
        if member_ids:
            accounts_result = await db.execute(
                select(Account).filter(Account.id.in_(member_ids))
            )
            accounts = accounts_result.scalars().all()
            member_names = [account.nickname or account.phone or f"用户{account.id}" for account in accounts]
        
        # 统计设备数和获取设备名字列表
        devices = await get_family_devices(db, family.id, skip=0, limit=1000)
        device_count = len(devices)
        device_ids = [d.id for d in devices]
        device_names = [d.name for d in devices]
        
        items.append({
            "id": family.id,
            "name": family.name,
            "avatar": family.avatar,
            "description": family.description,
            "inviteCode": family.invite_code,
            "memberCount": member_count,
            "memberIds": member_ids,
            "memberNames": member_names,
            "deviceCount": device_count,
            "deviceIds": device_ids,
            "deviceNames": device_names,
            "createdAt": family.created_at.strftime("%Y-%m-%d %H:%M:%S") if family.created_at else None,
            "updatedAt": family.updated_at.strftime("%Y-%m-%d %H:%M:%S") if family.updated_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.get("/family/{id}")
async def get_family_detail(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取家庭详情"""
    family = await get_family(db, id)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 获取成员ID列表
    members_result = await db.execute(
        select(FamilyMember.account_id).filter(FamilyMember.family_id == family.id)
    )
    member_ids = [row[0] for row in members_result.all()]
    
    # 获取设备ID列表
    devices = await get_family_devices(db, family.id, skip=0, limit=1000)
    device_ids = [d.id for d in devices]
    
    return {
        "id": family.id,
        "name": family.name,
        "avatar": family.avatar,
        "description": family.description,
        "inviteCode": family.invite_code,
        "memberIds": member_ids,
        "deviceIds": device_ids,
        "createdAt": family.created_at.strftime("%Y-%m-%d %H:%M:%S") if family.created_at else None,
        "updatedAt": family.updated_at.strftime("%Y-%m-%d %H:%M:%S") if family.updated_at else None
    }


@router.post("/family")
async def create_family_info(
    family_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建家庭"""
    # 验证必填字段
    if not family_data.get("name"):
        raise HTTPException(status_code=400, detail="家庭名称不能为空")
    
    # 生成邀请码
    invite_code = generate_invite_code()
    # 确保邀请码唯一
    from app.crud.family import get_family_by_invite_code
    while await get_family_by_invite_code(db, invite_code):
        invite_code = generate_invite_code()
    
    # 创建家庭
    family_create = FamilyCreate(
        name=family_data["name"],
        description=family_data.get("description"),
        avatar=family_data.get("avatar")
    )
    
    # 注意：这里需要一个创建者账号ID，但文档中没有要求，我们使用当前登录的管理员ID
    creator_account_id = extract_token_info(token_info)[0]
    if not creator_account_id:
        # 如果没有创建者，创建一个临时账号或者使用默认值
        # 这里我们暂时使用 None，但实际应该有一个创建者
        raise HTTPException(status_code=400, detail="需要创建者账号ID")
    
    # 获取创建者账号信息，判断是否是管理员
    from app.crud.account import get_account
    from app.models.account import AccountRole
    creator_account = await get_account(db, creator_account_id)
    is_admin = creator_account and creator_account.role == AccountRole.admin
    
    family = await create_family(db, family_create, creator_account_id)
    
    # 如果是管理员创建家庭，不自动加入家庭，需要删除自动创建的成员记录和设备关联
    if is_admin:
        # 删除自动创建的成员记录
        from app.crud.family_member import get_family_member_by_family_and_account, remove_family_member_by_family_and_account
        member = await get_family_member_by_family_and_account(db, family.id, creator_account_id)
        if member:
            await remove_family_member_by_family_and_account(db, family.id, creator_account_id)
        
        # 删除自动添加的设备关联
        from app.crud.family_device import get_family_devices, delete_family_device
        devices = await get_family_devices(db, family.id, skip=0, limit=1000)
        for device in devices:
            if device.account_id == creator_account_id:
                await delete_family_device(db, family.id, device.id)
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_create,
        description=f"创建家庭：{family.name}",
        extra={
            "family_id": family.id,
            "family_name": family.name,
            "invite_code": family.invite_code,
            "is_admin": is_admin
        }
    )
    
    return {
        "id": family.id,
        "name": family.name,
        "avatar": family.avatar,
        "description": family.description,
        "inviteCode": family.invite_code,
        "createdAt": family.created_at.strftime("%Y-%m-%d %H:%M:%S") if family.created_at else None,
        "updatedAt": family.updated_at.strftime("%Y-%m-%d %H:%M:%S") if family.updated_at else None
    }


@router.put("/family/{id}")
async def update_family_info(
    id: int,
    family_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新家庭信息"""
    # 验证家庭是否存在
    family = await get_family(db, id)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 构建更新数据
    family_update = FamilyUpdate()
    if "name" in family_data:
        family_update.name = family_data["name"]
    if "description" in family_data:
        family_update.description = family_data["description"]
    if "avatar" in family_data:
        family_update.avatar = family_data["avatar"]
    
    # 保存更新前的信息用于日志
    old_name = family.name
    
    updated_family = await update_family(db, id, family_update)
    if not updated_family:
        raise HTTPException(status_code=500, detail="更新失败")
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    changes = []
    if "name" in family_data and old_name != updated_family.name:
        changes.append(f"名称: {old_name} -> {updated_family.name}")
    if "description" in family_data:
        changes.append("更新描述")
    if "avatar" in family_data:
        changes.append("更新头像")
    
    log_description = f"更新家庭：{updated_family.name}" + (f" - {', '.join(changes)}" if changes else "")
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_update,
        description=log_description,
        extra={
            "family_id": updated_family.id,
            "old_name": old_name,
            "new_name": updated_family.name,
            "changes": changes
        }
    )
    
    return {
        "id": updated_family.id,
        "name": updated_family.name,
        "avatar": updated_family.avatar,
        "description": updated_family.description,
        "inviteCode": updated_family.invite_code,
        "updatedAt": updated_family.updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_family.updated_at else None
    }


@router.delete("/family/{id}")
async def delete_family_info(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除家庭"""
    # 验证家庭是否存在
    family = await get_family(db, id)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 保存家庭信息用于日志
    family_name = family.name
    family_invite_code = family.invite_code
    
    success = await delete_family(db, id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_delete,
        description=f"删除家庭：{family_name}",
        extra={
            "family_id": id,
            "family_name": family_name,
            "invite_code": family_invite_code
        }
    )
    
    return {}


@router.get("/family/{familyId}/members")
async def get_family_members(
    familyId: int,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取家庭成员列表"""
    skip = (page - 1) * pageSize
    
    # 验证家庭是否存在
    family = await get_family(db, familyId)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    members = await get_family_members_by_family(db, familyId, skip=skip, limit=pageSize)
    
    # 获取总数
    total_result = await db.execute(
        select(func.count(FamilyMember.id)).filter(FamilyMember.family_id == familyId)
    )
    total = total_result.scalar() or 0
    
    items = []
    for member in members:
        # 获取账号信息
        account_result = await db.execute(
            select(Account).filter(Account.id == member.account_id)
        )
        account = account_result.scalar_one_or_none()
        
        items.append({
            "id": member.id,
            "familyId": member.family_id,
            "accountId": member.account_id,
            "accountName": account.nickname if account else None,
            "nickname": member.nickname,
            "joinedAt": member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else None,
            "createdAt": member.created_at.strftime("%Y-%m-%d %H:%M:%S") if member.created_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.post("/family/{familyId}/members")
async def add_family_member(
    familyId: int,
    member_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """添加家庭成员"""
    # 验证家庭是否存在
    family = await get_family(db, familyId)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 验证必填字段
    if not member_data.get("accountId"):
        raise HTTPException(status_code=400, detail="账号ID不能为空")
    
    account_id = member_data["accountId"]
    
    # 验证用户是否存在
    from app.crud.account import get_account
    account = await get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 验证用户是否已经是该家庭的成员（避免重复添加）
    from app.crud.family_member import get_family_member_by_family_and_account
    existing_member = await get_family_member_by_family_and_account(db, familyId, account_id)
    if existing_member:
        raise HTTPException(status_code=400, detail="用户已经是该家庭的成员")
    
    # 创建家庭成员
    member_create = FamilyMemberCreate(
        family_id=familyId,
        account_id=account_id,
        nickname=member_data.get("nickname"),
        role="member"  # 默认角色为 member
    )
    
    member = await create_family_member(db, member_create)
    
    # 自动将该成员的所有设备添加到家庭
    from app.crud.family_device import add_account_devices_to_family
    await add_account_devices_to_family(db, account_id, familyId)
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_member_add,
        description=f"添加家庭成员：{account.nickname or account.phone} 到家庭 {family.name}",
        extra={
            "family_id": familyId,
            "family_name": family.name,
            "member_id": member.id,
            "account_id": account_id,
            "account_name": account.nickname or account.phone,
            "nickname": member.nickname
        }
    )
    
    return {
        "id": member.id,
        "familyId": member.family_id,
        "accountId": member.account_id,
        "accountName": account.nickname,
        "nickname": member.nickname,
        "joinedAt": member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else None,
        "createdAt": member.created_at.strftime("%Y-%m-%d %H:%M:%S") if member.created_at else None
    }


@router.put("/family/{familyId}/members/{memberId}")
async def update_family_member_nickname(
    familyId: int,
    memberId: int,
    member_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新家庭成员昵称"""
    # 验证家庭是否存在
    family = await get_family(db, familyId)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 验证成员是否存在
    from app.crud.family_member import get_family_member, update_family_member
    from app.models.family_member import FamilyMemberUpdate
    
    member = await get_family_member(db, memberId)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    if member.family_id != familyId:
        raise HTTPException(status_code=400, detail="成员不属于该家庭")
    
    # 构建更新数据
    member_update = FamilyMemberUpdate()
    if "nickname" in member_data:
        member_update.nickname = member_data["nickname"]
    else:
        raise HTTPException(status_code=400, detail="昵称参数不能为空")
    
    # 保存更新前的昵称用于日志
    old_nickname = member.nickname
    
    # 更新成员昵称
    updated_member = await update_family_member(db, memberId, member_update)
    if not updated_member:
        raise HTTPException(status_code=500, detail="更新失败")
    
    # 获取账号信息
    account_result = await db.execute(
        select(Account).filter(Account.id == updated_member.account_id)
    )
    account = account_result.scalar_one_or_none()
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_member_update,
        description=f"更新家庭成员昵称：{account.nickname if account else member.account_id} 在家庭 {family.name} - {old_nickname} -> {updated_member.nickname}",
        extra={
            "family_id": familyId,
            "family_name": family.name,
            "member_id": memberId,
            "account_id": updated_member.account_id,
            "old_nickname": old_nickname,
            "new_nickname": updated_member.nickname
        }
    )
    
    return {
        "id": updated_member.id,
        "familyId": updated_member.family_id,
        "accountId": updated_member.account_id,
        "accountName": account.nickname if account else None,
        "nickname": updated_member.nickname,
        "joinedAt": updated_member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if updated_member.joined_at else None,
        "createdAt": updated_member.created_at.strftime("%Y-%m-%d %H:%M:%S") if updated_member.created_at else None
    }


@router.delete("/family/{familyId}/members/{memberId}")
async def remove_family_member(
    familyId: int,
    memberId: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """移除家庭成员"""
    # 验证成员是否存在
    from app.crud.family_member import get_family_member
    member = await get_family_member(db, memberId)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    if member.family_id != familyId:
        raise HTTPException(status_code=400, detail="成员不属于该家庭")
    
    # 先移除该成员在该家庭中的所有设备
    from app.crud.family_device import delete_account_devices_from_family
    removed_device_count = await delete_account_devices_from_family(db, member.account_id, familyId)
    
    # 保存成员信息用于日志
    from app.crud.account import get_account
    account = await get_account(db, member.account_id)
    account_name = account.nickname if account else None
    family = await get_family(db, familyId)
    family_name = family.name if family else None
    
    # 删除成员关联关系
    success = await remove_family_member_by_family_and_account(db, familyId, member.account_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_member_remove,
        description=f"移除家庭成员：{account_name or member.account_id} 从家庭 {family_name or familyId}",
        extra={
            "family_id": familyId,
            "family_name": family_name,
            "member_id": memberId,
            "account_id": member.account_id,
            "account_name": account_name,
            "removed_device_count": removed_device_count
        }
    )
    
    return {}


@router.post("/family/{familyId}/devices/{deviceId}")
async def add_family_device(
    familyId: int,
    deviceId: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """将设备添加到家庭（在 family_device 表中创建关联）"""
    # 验证家庭是否存在
    family = await get_family(db, familyId)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 验证设备是否存在
    from app.crud.device import get_device
    device = await get_device(db, deviceId)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备是否已在家庭中
    from app.crud.family_device import check_device_in_family, create_family_device
    if await check_device_in_family(db, deviceId, familyId):
        raise HTTPException(status_code=400, detail="设备已在此家庭中")
    
    # 添加设备到家庭
    family_device = await create_family_device(db, familyId, deviceId)
    if not family_device:
        raise HTTPException(status_code=500, detail="设备添加失败")
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_add_to_family,
        description=f"添加设备到家庭：{device.name}（SN: {device.sn}）到家庭 {family.name}",
        extra={
            "family_id": familyId,
            "family_name": family.name,
            "device_id": deviceId,
            "device_name": device.name,
            "device_sn": device.sn
        }
    )
    
    return {
        "message": "设备已添加到家庭",
        "familyId": familyId,
        "familyName": family.name,
        "deviceId": deviceId,
        "deviceName": device.name,
        "deviceSn": device.sn
    }


@router.delete("/family/{familyId}/devices/{deviceId}")
async def remove_family_device(
    familyId: int,
    deviceId: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """从家庭中移除设备（删除 family_device 表中的关联）"""
    # 验证家庭是否存在
    family = await get_family(db, familyId)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 验证设备是否存在
    from app.crud.device import get_device
    device = await get_device(db, deviceId)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备是否属于该家庭
    from app.crud.family_device import check_device_in_family
    if not await check_device_in_family(db, deviceId, familyId):
        raise HTTPException(status_code=404, detail="设备不属于此家庭")
    
    # 移除设备与家庭的关联
    from app.crud.family_device import delete_family_device
    success = await delete_family_device(db, familyId, deviceId)
    if not success:
        raise HTTPException(status_code=500, detail="删除设备关联失败")
    
    # 记录操作日志
    from app.models.user_operation_log import OperationTypeEnum
    
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_remove_from_family,
        description=f"从家庭移除设备：{device.name}（SN: {device.sn}）从家庭 {family.name}",
        extra={
            "family_id": familyId,
            "family_name": family.name,
            "device_id": deviceId,
            "device_name": device.name,
            "device_sn": device.sn
        }
    )
    
    return {
        "message": "设备已从家庭中移除",
        "familyId": familyId,
        "deviceId": deviceId,
        "deviceName": device.name
    }

