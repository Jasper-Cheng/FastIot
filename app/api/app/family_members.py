from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.crud.family import get_family_by_invite_code, get_family
from app.crud.family_member import (
    get_family_members_by_family,
    get_family_member,
    get_family_member_by_family_and_account,
    create_family_member,
    update_family_member,
    delete_family_member
)
from app.crud.user_operation_log import user_operation_log
from app.models.family_member import (
    FamilyMemberCreate,
    FamilyMemberUpdate,
    FamilyMemberInDB,
    FamilyMemberWithAccount,
    FamilyMemberRole,
    JoinByInviteCodeRequest
)
from app.models.family import FamilyInDB
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.services.mqtt_service import mqtt_service

router = APIRouter()


@router.get("/family/{family_id}", response_model=List[FamilyMemberWithAccount])
async def list_family_members(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """获取家庭成员列表"""
    account_id = token_info["account_id"]
    
    # 检查是否是家庭成员
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    family_members = await get_family_members_by_family(db, family_id, skip=skip, limit=limit)
    # 转换为包含 account 信息的响应模型
    return [
        FamilyMemberWithAccount(
            id=member.id,
            family_id=member.family_id,
            role=member.role,
            nickname=member.nickname,
            joined_at=member.joined_at,
            created_at=member.created_at,
            account=member.account
        )
        for member in family_members
    ]


@router.post("/join-by-invite-code", response_model=FamilyInDB)
async def join_family_by_invite_code(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    request: JoinByInviteCodeRequest = Body(...)
):
    """通过邀请码加入家庭"""
    account_id = token_info["account_id"]
    
    # 根据邀请码查找家庭
    family = await get_family_by_invite_code(db, request.invite_code)
    if not family:
        raise HTTPException(status_code=404, detail="邀请码无效")
    
    # 检查是否已经是家庭成员
    existing_member = await get_family_member_by_family_and_account(db, family.id, account_id)
    if existing_member:
        raise HTTPException(status_code=400, detail="您已经是该家庭的成员")
    
    # 创建家庭成员记录
    member_data = FamilyMemberCreate(
        family_id=family.id,
        account_id=account_id,
        nickname=request.nickname or "家庭成员",
        role=FamilyMemberRole.member
    )
    
    new_member = await create_family_member(db, member_data)
    if not new_member:
        raise HTTPException(status_code=400, detail="加入家庭失败")
    
    # 记录操作日志
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.family_join,
                description=f"通过App加入家庭: {family.name}",
                extra={
                    "family_id": family.id,
                    "family_name": family.name,
                    "invite_code": request.invite_code,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        print(f"记录加入家庭操作日志失败: {e}")
    
    # 发送家庭消息通知新成员加入
    try:
        role = token_info.get("role")
        await mqtt_service.publish_home_notice(
            home_id=str(family.id),
            payload={
                "method": "family.message",
                "params": {
                    "type": "member.join",
                    "data": {
                        "senderId": account_id,
                        "senderRole": role,
                        "title": "新成员加入",
                        "message": f"{request.nickname or '新成员'} 加入了家庭",
                        "level": "normal",
                        "familyId": family.id,
                        "familyName": family.name
                    }
                }
            }
        )
    except Exception as e:
        print(f"发送新成员加入消息失败: {e}")
    
    return FamilyInDB.model_validate(family)


@router.patch("/{id}", response_model=FamilyMemberInDB)
async def update_member_info(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    update_data: FamilyMemberUpdate = Body(...)
):
    """更新成员信息（只能更新自己的信息）"""
    account_id = token_info["account_id"]
    
    # 获取成员信息
    member = await get_family_member(db, id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 只能更新自己的信息
    if member.account_id != account_id:
        raise HTTPException(status_code=403, detail="只能修改自己的信息")
    
    # 更新成员信息
    updated_member = await update_family_member(db, id, update_data)
    if not updated_member:
        raise HTTPException(status_code=404, detail="更新失败")
    
    # 记录操作日志
    try:
        family = await get_family(db, member.family_id)
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.family_member_update,
                description=f"通过App更新家庭成员信息",
                extra={
                    "family_id": member.family_id,
                    "family_name": family.name if family else None,
                    "member_id": id,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        print(f"记录更新成员信息操作日志失败: {e}")
    
    return FamilyMemberInDB.model_validate(updated_member)


@router.delete("/{id}")
async def remove_member(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """移除家庭成员
    
    - 创建者可以移除任何成员（除了自己）
    - 成员只能移除自己（退出家庭）
    """
    account_id = token_info["account_id"]
    
    # 获取成员信息
    member = await get_family_member(db, id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 获取当前用户在该家庭的成员信息
    current_member = await get_family_member_by_family_and_account(db, member.family_id, account_id)
    if not current_member:
        raise HTTPException(status_code=403, detail="您不是该家庭的成员")
    
    # 权限检查
    if member.account_id != account_id:
        # 要移除其他成员，必须是创建者
        if current_member.role != FamilyMemberRole.creator:
            raise HTTPException(status_code=403, detail="只有创建者可以移除其他成员")
    
    # 创建者不能移除自己
    if member.role == FamilyMemberRole.creator and member.account_id == account_id:
        raise HTTPException(status_code=400, detail="创建者不能退出家庭，请先转让或删除家庭")
    
    # 删除成员
    success = await delete_family_member(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="移除失败")
    
    # 记录操作日志
    try:
        family = await get_family(db, member.family_id)
        action = "退出" if member.account_id == account_id else "移除成员"
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.family_member_remove,
                description=f"通过App{action}家庭: {family.name if family else member.family_id}",
                extra={
                    "family_id": member.family_id,
                    "family_name": family.name if family else None,
                    "member_id": id,
                    "action": action,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        print(f"记录移除成员操作日志失败: {e}")
    
    # 发送家庭消息通知成员移除
    try:
        role = token_info.get("role")
        family = await get_family(db, member.family_id)
        await mqtt_service.publish_home_notice(
            home_id=str(member.family_id),
            payload={
                "method": "family.message",
                "params": {
                    "type": "member.remove",
                    "data": {
                        "senderId": account_id,
                        "senderRole": role,
                        "title": "成员移除",
                        "message": f"成员已{action}",
                        "level": "warning",
                        "familyId": member.family_id,
                        "familyName": family.name if family else None
                    }
                }
            }
        )
    except Exception as e:
        print(f"发送成员移除消息失败: {e}")
    
    return {}

