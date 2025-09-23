from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel, constr
from app.models.account import AccountGender, AccountUpdate

from app.db.session import get_db
from app.crud.user import get_users, get_user, create_user, delete_user
from app.crud.account import get_account, update_account, get_account_by_account_name, get_account_by_phone, get_account_by_email
from app.models.user import User, UserCreate, UserInDB
router = APIRouter()


class UserUpdateRequest(BaseModel):
    """用户信息更新请求
    
    所有字段都是可选的，至少需要提供一个字段进行更新
    """
    account: str | None = None
    name: str | None = None
    gender: AccountGender | None = None
    phone: constr(pattern=r"^1\d{10}$") | None = None
    email: str | None = None
    avatar: str | None = None
    password: str | None = None


@router.get("/", response_model=List[User])
async def list_users(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    return await get_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=User)
async def get_user_detail(
    user_id: int, 
    db: AsyncSession = Depends(get_db),
):
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}", response_model=User)
async def update_user_detail(
    user_id: int, 
    payload: UserUpdateRequest, 
    db: AsyncSession = Depends(get_db),
):
    """更新用户信息
    
    更新用户的账号信息，包括账号名、姓名、性别、手机号、邮箱、头像、密码等
    """
    # 读取用户
    u = await get_user(db, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 至少提供一个可更新字段
    if not any([
        payload.account is not None,
        payload.name is not None,
        payload.gender is not None,
        payload.phone is not None,
        payload.email is not None,
        payload.avatar is not None,
        payload.password is not None,
    ]):
        raise HTTPException(status_code=400, detail="至少提供一个可更新字段")

    # 变更账号名时校验唯一且非空
    if payload.account is not None:
        new_acc = payload.account.strip()
        if new_acc == "":
            raise HTTPException(status_code=400, detail="account 不能为空")
        # 加载当前账号（避免触发关系懒加载）
        current_acc = await get_account(db, u.account_id)
        current_login = current_acc.account if current_acc else None
        if new_acc != current_login:
            existed = await get_account_by_account_name(db, new_acc)
            if existed and existed.id != u.account_id:
                raise HTTPException(status_code=400, detail="账号已存在")

    # 变更手机号时检重
    if payload.phone is not None:
        existed_phone = await get_account_by_phone(db, payload.phone)
        if existed_phone and existed_phone.id != u.account_id:
            raise HTTPException(status_code=400, detail="手机号已被使用")

    # 规范化并检重邮箱
    norm_email = None
    if payload.email is not None:
        v = (payload.email or "").strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None
        else:
            norm_email = v
            existed_email = await get_account_by_email(db, norm_email)
            if existed_email and existed_email.id != u.account_id:
                raise HTTPException(status_code=400, detail="邮箱已被使用")

    # 仅传递有值的字段
    updated: dict = {}
    if payload.account is not None:
        updated["account"] = payload.account.strip()
    if payload.name is not None:
        updated["name"] = payload.name
    if payload.gender is not None:
        updated["gender"] = payload.gender  # type: ignore[assignment]
    if payload.phone is not None:
        updated["phone"] = payload.phone
    if payload.email is not None:
        updated["email"] = norm_email
    if payload.avatar is not None:
        updated["avatar"] = payload.avatar
    if payload.password is not None:
        updated["password"] = payload.password

    await update_account(
        db,
        u.account_id,
        AccountUpdate(**updated),
    )

    # 重新返回用户（包含 account 信息）
    u = await get_user(db, user_id)
    return u


@router.delete("/{user_id}")
async def remove_user(
    user_id: int, 
    db: AsyncSession = Depends(get_db),
):
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


