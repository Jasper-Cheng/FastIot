from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from typing import List, Optional

from app.crud.family import get_family, get_family_by_invite_code, delete_family
from app.crud.family_member import (
    get_family_member,
    get_family_member_by_family_and_account,
    get_family_members_by_family,
    create_family_member,
    update_family_member as crud_update_family_member,
    delete_family_member,
)
from app.crud.account import get_account
from app.db.models.family_member import FamilyMember as FamilyMemberModel
from app.models.family_member import (
    FamilyMemberCreate,
    FamilyMemberUpdate,
    FamilyMemberInDB,
    FamilyMemberWithAccount,
    FamilyMemberRole,
    JoinFamilyRequest
)
from app.models.user_operation_log import OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.api.utils import (
    extract_token_info,
    log_operation_with_token,
    check_family_member,
    send_family_notice
)

router = APIRouter()

"""
家庭成员管理模块 - Client API

【App + Web 通用】
所有接口支持 App 和 Web 平台，平台信息通过 token.platform 字段识别。
"""


@router.post("/join-by-invite-code")
async def join_family_by_invite_code(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    invite_code: str = Query(..., description="家庭邀请码"),
    request: Optional[JoinFamilyRequest] = Body(None, description="加入家庭请求，包含可选的nickname"),
):
    """通过邀请码加入家庭"""
    account_id, _, _ = extract_token_info(token_info)
    
    # 查找家庭
    family = await get_family_by_invite_code(db, invite_code)
    if not family:
        raise HTTPException(status_code=404, detail="邀请码无效")
    
    # 检查是否已经是家庭成员
    existing = await get_family_member_by_family_and_account(db, family.id, account_id)
    if existing:
        raise HTTPException(status_code=400, detail="您已经是该家庭的成员")
    
    # 确定nickname：优先使用请求中的nickname，否则获取账号信息使用account的nickname
    nickname = None
    if request and request.nickname:
        nickname = request.nickname
    else:
        # 只有在没有提供nickname时才获取账号信息
        account = await get_account(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        if account.nickname:
            nickname = account.nickname
    
    # 创建家庭成员记录
    family_member = await create_family_member(
        db,
        FamilyMemberCreate(
            family_id=family.id,
            account_id=account_id,
            role=FamilyMemberRole.member,
            nickname=nickname
        )
    )
    
    # 自动将该成员的所有设备添加到家庭
    from app.crud.family_device import add_account_devices_to_family
    await add_account_devices_to_family(db, account_id, family.id)
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_member_add,
        description=f"加入家庭: {family.name}",
        extra={"family_id": family.id, "family_name": family.name}
    )
    
    # 发送家庭通知
    await send_family_notice(
        family_id=family.id,
        payload={
            "type": "family_member_added",
            "message": f"家庭成员 {nickname} 已加入家庭 {family.name}",
            "family_id": family.id,
            "family_name": family.name,
            "operator_account_id": account_id
        }
    )
    
    return family_member


@router.get("/family/{family_id}", response_model=List[FamilyMemberWithAccount])
async def list_family_members(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """获取家庭成员列表"""
    account_id, _, _ = extract_token_info(token_info)
    
    # 检查是否是家庭成员
    await check_family_member(db, family_id, account_id)
    
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


@router.patch("/{family_member_id}", response_model=FamilyMemberWithAccount)
async def update_family_member(
    family_member_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    family_member: FamilyMemberUpdate = Body(...)
):
    """更新家庭成员昵称
    
    权限说明：
    - 创建者可以修改任何成员的昵称
    - 普通成员只能修改自己的昵称
    """
    account_id, _, _ = extract_token_info(token_info)
    
    db_family_member = await get_family_member(db, family_member_id)
    if not db_family_member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    
    # 检查权限：创建者可以修改任何成员，普通成员只能修改自己
    if db_family_member.account_id != account_id:
        # 如果不是修改自己，检查是否是创建者
        current_member = await get_family_member_by_family_and_account(
            db, db_family_member.family_id, account_id
        )
        if not current_member or current_member.role != FamilyMemberRole.creator:
            raise HTTPException(status_code=403, detail="无权修改其他成员的昵称")
    
    # 记录更新前的昵称
    old_nickname = db_family_member.nickname
    
    # 只允许更新nickname
    updated = await crud_update_family_member(db, family_member_id, family_member)
    if not updated:
        raise HTTPException(status_code=404, detail="更新家庭成员信息失败")
    
    # 获取家庭信息用于日志
    family = await get_family(db, db_family_member.family_id)
    family_name = family.name if family else None
    
    # 获取被更新成员的账号信息
    target_account = await get_account(db, db_family_member.account_id)
    target_account_name = target_account.nickname if target_account and target_account.nickname else target_account.phone if target_account else "成员"
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_member_update,
        description=f"更新家庭成员昵称：{old_nickname or '未设置'} -> {family_member.nickname or '未设置'}",
        extra={
            "family_id": db_family_member.family_id,
            "family_name": family_name,
            "member_id": db_family_member.account_id,
            "member_name": target_account_name,
            "old_nickname": old_nickname,
            "new_nickname": family_member.nickname
        }
    )
    
    # 发送家庭通知
    await send_family_notice(
        family_id=db_family_member.family_id,
        payload={
            "type": "family_member_updated",
            "message": f"家庭成员昵称已更新：{old_nickname or '未设置'} -> {family_member.nickname or '未设置'}",
            "family_id": db_family_member.family_id,
            "family_name": family_name,
            "operator_account_id": account_id
        }
    )
    
    # 重新加载以获取关联的account信息
    result = await db.execute(
        select(FamilyMemberModel)
        .options(selectinload(FamilyMemberModel.account))
        .filter(FamilyMemberModel.id == family_member_id)
    )
    updated_with_account = result.scalar_one_or_none()
    
    if not updated_with_account:
        raise HTTPException(status_code=404, detail="获取更新后的成员信息失败")
    
    # 转换为包含 account 信息的响应模型
    return FamilyMemberWithAccount(
        id=updated_with_account.id,
        family_id=updated_with_account.family_id,
        role=updated_with_account.role,
        nickname=updated_with_account.nickname,
        joined_at=updated_with_account.joined_at,
        created_at=updated_with_account.created_at,
        account=updated_with_account.account
    )


@router.delete("/{family_member_id}")
async def remove_family_member(
    family_member_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """移除家庭成员
    
    - 如果当前成员是创建者，可以移除该家庭的任何成员
    - 如果不是创建者，只能移除自己
    - 如果移除的是创建者自己，则删除整个家庭
    """
    account_id, _, _ = extract_token_info(token_info)
    
    # 获取要移除的成员信息
    db_family_member = await get_family_member(db, family_member_id)
    if not db_family_member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    
    # 获取当前用户在同一个家庭中的成员信息
    current_member = await get_family_member_by_family_and_account(
        db, db_family_member.family_id, account_id
    )
    if not current_member:
        raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    # 检查权限：如果不是创建者，只能移除自己
    if current_member.role != FamilyMemberRole.creator and db_family_member.account_id != account_id:
        raise HTTPException(status_code=403, detail="只能移除自己")
    
    # 提前获取家庭和被移除成员的信息
    family = await get_family(db, db_family_member.family_id)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    removed_account = await get_account(db, db_family_member.account_id)
    family_id = db_family_member.family_id
    family_name = family.name
    
    # 如果要移除的是创建者，删除整个家庭
    if db_family_member.role == FamilyMemberRole.creator:
        success = await delete_family(db, family_id)
        if not success:
            raise HTTPException(status_code=404, detail="删除家庭失败")
        
        # 记录操作日志
        await log_operation_with_token(
            db=db,
            token_info=token_info,
            operation_type=OperationTypeEnum.family_delete,
            description=f"删除家庭: {family_name}",
            extra={"family_id": family_id, "family_name": family_name}
        )
        
        # 发送家庭通知
        await send_family_notice(
            family_id=family_id,
            payload={
                "type": "family_deleted",
                "message": f"家庭 {family_name} 已被删除",
                "family_id": family_id,
                "family_name": family_name,
                "operator_account_id": account_id
            }
        )
        
        return {"message": "家庭已删除"}
    
    # 移除普通成员前，先移除该成员在该家庭中的所有设备
    from app.crud.family_device import delete_account_devices_from_family
    removed_device_count = await delete_account_devices_from_family(
        db, db_family_member.account_id, family_id
    )
    if removed_device_count > 0:
        print(f"已从家庭 {family_name} 中移除成员 {db_family_member.account_id} 的 {removed_device_count} 个设备")
    
    # 移除普通成员
    success = await delete_family_member(db, family_member_id)
    if not success:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    
    removed_member_name = removed_account.nickname if removed_account and removed_account.nickname else removed_account.phone if removed_account else "成员"
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_member_remove,
        description=f"移除家庭成员: {removed_member_name}",
        extra={
            "family_id": family_id,
            "family_name": family_name,
            "removed_account_id": db_family_member.account_id
        }
    )
    
    # 发送家庭通知
    await send_family_notice(
        family_id=family_id,
        payload={
            "type": "family_member_removed",
            "message": f"家庭成员 {removed_member_name} 已从家庭 {family_name} 中移除",
            "family_id": family_id,
            "family_name": family_name,
            "operator_account_id": account_id
        }
    )
    
    return {"message": "成员已移除"}

