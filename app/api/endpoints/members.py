from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db
from app.crud.member import (
    get_member, get_members_by_user, create_member, update_member, delete_member,
    get_member_by_account, verify_member_password
)
from app.models.member import Member, MemberCreate, MemberUpdate, MemberLogin
from app.models.user import User
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[Member], tags=["members"])
async def read_members(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的成员列表"""
    members = await get_members_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return members

@router.post("/", response_model=Member, tags=["members"])
async def create_new_member(
    member: MemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新成员"""
    # 确保成员属于当前用户
    if member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能为其他用户创建成员"
        )
    
    # 检查账号是否已存在
    if member.account:
        existing_member = await get_member_by_account(db, member.account)
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="账号已存在"
            )
    
    return await create_member(db=db, member=member)

@router.get("/{member_id}", response_model=Member, tags=["members"])
async def read_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定成员信息"""
    member = await get_member(db, member_id=member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 检查成员是否属于当前用户
    if member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该成员信息"
        )
    
    return member

@router.put("/{member_id}", response_model=Member, tags=["members"])
async def update_member_info(
    member_id: int,
    member: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新成员信息"""
    db_member = await get_member(db, member_id=member_id)
    if db_member is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 检查成员是否属于当前用户
    if db_member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改该成员信息"
        )
    
    # 如果更新账号，检查是否已存在
    if member.account and member.account != db_member.account:
        existing_member = await get_member_by_account(db, member.account)
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="账号已存在"
            )
    
    updated_member = await update_member(db=db, member_id=member_id, member=member)
    if updated_member is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    return updated_member

@router.delete("/{member_id}", tags=["members"])
async def delete_member_info(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除成员"""
    db_member = await get_member(db, member_id=member_id)
    if db_member is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 检查成员是否属于当前用户
    if db_member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除该成员"
        )
    
    success = await delete_member(db=db, member_id=member_id)
    if not success:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    return {"message": "成员删除成功"}

@router.post("/login", tags=["members"])
async def member_login(
    member_login: MemberLogin,
    db: AsyncSession = Depends(get_db)
):
    """成员登录"""
    member = await get_member_by_account(db, member_login.account)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    
    if not verify_member_password(member, member_login.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    
    # 这里应该生成JWT token，简化处理
    return {
        "message": "登录成功",
        "member_id": member.id,
        "member_name": member.name,
        "user_id": member.user_id
    }
