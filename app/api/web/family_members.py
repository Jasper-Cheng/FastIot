from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from typing import List, Optional

from app.crud.family import get_family, get_family_by_invite_code
from app.crud.family_member import (
    get_family_member,
    get_family_member_by_family_and_account,
    get_family_members_by_family,
    create_family_member,
    update_family_member as crud_update_family_member,
    delete_family_member,
    remove_family_member_by_family_and_account
)
from app.crud.account import get_account
from app.crud.user_operation_log import user_operation_log
from app.db.models.family_member import FamilyMember as FamilyMemberModel
from app.models.family_member import (
    FamilyMemberCreate,
    FamilyMemberUpdate,
    FamilyMemberInDB,
    FamilyMemberWithAccount,
    FamilyMemberRole,
    JoinFamilyRequest
)
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db

router = APIRouter()


@router.post("/join-by-invite-code")
async def join_family_by_invite_code(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    invite_code: str = Query(..., description="家庭邀请码"),
    request: Optional[JoinFamilyRequest] = Body(None, description="加入家庭请求，包含可选的nickname"),
):
    """通过邀请码加入家庭"""
    account_id = token_info["account_id"]
    
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
    await user_operation_log.create(
        db=db,
        obj_in=UserOperationLogCreate(
            operation_type=OperationTypeEnum.family_member_add,
            description=f"加入家庭: {family.name}",
            extra={"family_id": family.id, "family_name": family.name}
        ),
        account_id=account_id
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
    account_id = token_info["account_id"]
    
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
    
    # 只允许更新nickname（nickname可以为None，表示清空昵称）
    updated = await crud_update_family_member(db, family_member_id, family_member)
    if not updated:
        raise HTTPException(status_code=404, detail="更新家庭成员信息失败")
    
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
    """移除家庭成员（创建者可以移除任何人，成员只能移除自己）
    
    如果移除的是创建者，则删除整个家庭。
    """
    account_id = token_info["account_id"]
    
    db_family_member = await get_family_member(db, family_member_id)
    if not db_family_member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    
    # 如果移除的是创建者，删除整个家庭
    if db_family_member.role == FamilyMemberRole.creator:
        family = await get_family(db, db_family_member.family_id)
        if not family:
            raise HTTPException(status_code=404, detail="家庭不存在")
        
        # 检查权限：只有创建者自己可以删除家庭
        if db_family_member.account_id != account_id:
            raise HTTPException(status_code=403, detail="无权删除此家庭")
        
        family_name = family.name
        
        # 记录删除家庭的操作日志
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.family_delete,
                description=f"删除家庭: {family_name}（移除创建者时自动删除）",
                extra={
                    "family_id": family.id,
                    "family_name": family_name,
                    "reason": "creator_removed"
                }
            ),
            account_id=account_id
        )
        
        # 删除家庭（会级联删除所有家庭成员和设备关联）
        from app.crud.family import delete_family
        success = await delete_family(db, family.id)
        if not success:
            raise HTTPException(status_code=404, detail="删除家庭失败")
        
        return {"message": "家庭已删除（创建者已移除）"}
    
    # 移除普通成员
    # 检查权限
    family_creator = await get_family_member_by_family_and_account(
        db, db_family_member.family_id, account_id
    )
    
    # 如果是创建者，可以移除任何人（但不能移除自己）
    if family_creator and family_creator.role == FamilyMemberRole.creator:
        if db_family_member.account_id == account_id:
            raise HTTPException(status_code=400, detail="创建者不能移除自己，请先转让创建者权限")
    # 如果是成员，只能移除自己
    elif db_family_member.account_id != account_id:
        raise HTTPException(status_code=403, detail="无权移除其他成员")
    
    family = await get_family(db, db_family_member.family_id)
    removed_account = await get_account(db, db_family_member.account_id)
    
    success = await delete_family_member(db, family_member_id)
    if not success:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    
    # 记录操作日志
    await user_operation_log.create(
        db=db,
        obj_in=UserOperationLogCreate(
            operation_type=OperationTypeEnum.family_member_remove,
            description=f"移除家庭成员: {removed_account.nickname or removed_account.phone}",
            extra={
                "family_id": db_family_member.family_id,
                "family_name": family.name if family else None,
                "removed_account_id": db_family_member.account_id
            }
        ),
        account_id=account_id
    )
    
    return {"message": "成员已移除"}

