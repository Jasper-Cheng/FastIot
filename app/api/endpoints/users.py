from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.crud.user import get_users, get_user, create_user, delete_user
from app.models.user import User, UserCreate

router = APIRouter()


@router.get("/", response_model=List[User])
async def list_users(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    return await get_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=User)
async def get_user_detail(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.post("/", response_model=User)
async def create_user_binding(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    # 仅绑定已存在的 owner 账号（account_id 必须存在且唯一）
    if not getattr(payload, "account_id", None):
        raise HTTPException(status_code=400, detail="account_id 为必填")
    return await create_user(db, payload)


@router.delete("/{user_id}")
async def remove_user(user_id: int, db: AsyncSession = Depends(get_db)):
    ok = await delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "删除成功"}


