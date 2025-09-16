from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.admin import Admin as AdminModel, AdminInDB, AdminBase, Admin
from app.crud.admin import (
    get_admins,
    get_admin,
    get_admin_by_account_id,
    create_admin,
    delete_admin,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/", response_model=List[Admin])
async def list_admins(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    return await get_admins(db, skip=skip, limit=limit)


@router.get("/{admin_id}", response_model=Admin)
async def get_admin_detail(admin_id: int, db: AsyncSession = Depends(get_db)):
    admin = await get_admin(db, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="管理员不存在")
    return admin


