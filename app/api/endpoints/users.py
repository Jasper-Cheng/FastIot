from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.crud.user import get_users, get_user, create_user, delete_user
from app.models.user import User, UserCreate, UserInDB
from app.api.dependencies import get_current_guard, ensure_owner_or_admin, require_roles

router = APIRouter(dependencies=[Depends(require_roles(["member", "owner", "admin"]))])


@router.get("/", response_model=List[User])
async def list_users(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    guard: dict = Depends(get_current_guard),
):
    # admin 可查看任意；owner 仅查看自己
    if guard.get("role") == "admin":
        return await get_users(db, skip=skip, limit=limit)
    user = await get_user(db, guard.get("user_id") or guard.get("owner_user_id"))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return [user]


@router.get("/{user_id}", response_model=User)
async def get_user_detail(
    user_id: int, 
    db: AsyncSession = Depends(get_db),
    guard: dict = Depends(get_current_guard),
):
    ensure_owner_or_admin(user_id, guard)
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.delete("/{user_id}")
async def remove_user(
    user_id: int, 
    db: AsyncSession = Depends(get_db),
    guard: dict = Depends(get_current_guard),
):
    ensure_owner_or_admin(user_id, guard)
    """删除用户
    
    删除用户时会：
    - 将该用户的所有设备状态更新为 unbound，user_id 设为 NULL
    - 删除该用户下的所有成员
    - 删除该用户的所有房间
    - 删除该用户的账号信息
    - 设备保留但变为未绑定状态，可以被其他用户重新激活
    """
    ok = await delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "删除成功，该用户的设备已变为未绑定状态"}


