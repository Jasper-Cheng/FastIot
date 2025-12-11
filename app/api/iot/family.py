from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select, func
from datetime import datetime

from app.db.session import get_db
from app.api.dependencies import get_current_token
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
        
        # 获取成员ID列表
        members_result = await db.execute(
            select(FamilyMember.account_id).filter(FamilyMember.family_id == family.id)
        )
        member_ids = [row[0] for row in members_result.all()]
        
        # 统计设备数
        devices = await get_family_devices(db, family.id, skip=0, limit=1000)
        device_count = len(devices)
        device_ids = [d.id for d in devices]
        
        items.append({
            "id": family.id,
            "name": family.name,
            "avatar": family.avatar,
            "description": family.description,
            "inviteCode": family.invite_code,
            "memberCount": member_count,
            "memberIds": member_ids,
            "deviceCount": device_count,
            "deviceIds": device_ids,
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
    creator_account_id = token_info.get("account_id")
    if not creator_account_id:
        # 如果没有创建者，创建一个临时账号或者使用默认值
        # 这里我们暂时使用 None，但实际应该有一个创建者
        raise HTTPException(status_code=400, detail="需要创建者账号ID")
    
    family = await create_family(db, family_create, creator_account_id)
    
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
    
    updated_family = await update_family(db, id, family_update)
    if not updated_family:
        raise HTTPException(status_code=500, detail="更新失败")
    
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
    
    success = await delete_family(db, id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
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
    
    return {
        "id": member.id,
        "familyId": member.family_id,
        "accountId": member.account_id,
        "accountName": account.nickname,
        "nickname": member.nickname,
        "joinedAt": member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else None,
        "createdAt": member.created_at.strftime("%Y-%m-%d %H:%M:%S") if member.created_at else None
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
    
    # 删除成员关联关系
    success = await remove_family_member_by_family_and_account(db, familyId, member.account_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {}

