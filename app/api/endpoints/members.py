from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel, constr

from app.db.session import get_db
from app.crud.member import get_members_by_user, get_member, create_member, update_member, delete_member
from app.crud.user import get_user
from sqlalchemy import select
from app.db.models.device import Device
from app.db.models.member_device_permission import MemberDevicePermission
from app.crud.account import create_account, get_account_by_account_name, get_account_by_phone, get_account_by_email, update_account, get_account, delete_account
from app.models.member import Member, MemberCreate, MemberUpdate, MemberInDB
from app.models.account import AccountCreate, AccountRole, AccountGender, AccountUpdate
from app.api.dependencies import get_current_guard, ensure_owner_or_admin, require_roles

router = APIRouter(dependencies=[Depends(require_roles(["member", "owner", "admin"]))])


@router.get("/", response_model=List[Member], response_model_exclude={"user"})
async def list_members(
    user_id: int, 
    db: AsyncSession = Depends(get_db), 
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, ge=1, le=200),
    guard: dict = Depends(get_current_guard),
):
    ensure_owner_or_admin(user_id, guard)
    return await get_members_by_user(db, user_id=user_id, skip=skip, limit=limit)


@router.get("/{member_id}", response_model=Member, response_model_exclude={"user"})
async def get_member_detail(
    member_id: int, 
    db: AsyncSession = Depends(get_db),
    guard: dict = Depends(get_current_guard),
):
    m = await get_member(db, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="成员不存在")
    # 允许：管理员；该成员本人；或该成员所属用户
    if guard.get("role") == "admin" or guard.get("member_id") == member_id:
        return m
    ensure_owner_or_admin(m.user_id, guard)
    return m


class MemberRegisterRequest(BaseModel):
    """创建成员（子账号）

    必填: user_id(归属主账号), account(登录名), password(密码), phone(手机号)
    可选: name, gender, email, avatar
    说明: role 不可填写，强制为 member
    """
    user_id: int
    account: str
    password: str
    phone: constr(pattern=r"^1\d{10}$")
    name: str | None = None
    gender: AccountGender | None = None
    email: str | None = None
    avatar: str | None = None


@router.post("/", response_model=MemberInDB)
async def create_member_for_user(
    payload: MemberRegisterRequest, 
    db: AsyncSession = Depends(get_db),
    guard: dict = Depends(get_current_guard),
):
    ensure_owner_or_admin(payload.user_id, guard)
    # 校验 user 是否存在
    owner = await get_user(db, payload.user_id)
    if not owner:
        raise HTTPException(status_code=400, detail="归属的用户不存在")

    # 规范化可选字符串字段
    norm_email = (payload.email or None)
    if norm_email:
        v = norm_email.strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None

    # 校验账号唯一
    exists = await get_account_by_account_name(db, payload.account)
    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")

    # 校验手机号唯一
    phone_exists = await get_account_by_phone(db, payload.phone)
    if phone_exists:
        raise HTTPException(status_code=400, detail="手机号已被使用")

    # 校验邮箱唯一（如果提供）
    if norm_email:
        email_exists = await get_account_by_email(db, norm_email)
        if email_exists:
            raise HTTPException(status_code=400, detail="邮箱已被使用")

    # 1) 先创建 account，role 强制为 member
    acc = await create_account(
        db,
        AccountCreate(
            account=payload.account,
            password=payload.password,
            phone=payload.phone,
            name=payload.name,
            gender=payload.gender,  # type: ignore[arg-type]
            email=norm_email,
            avatar=payload.avatar,
            role=AccountRole.member,
        ),
    )

    # 2) 创建 member 绑定 user_id 与 account_id
    m = await create_member(
        db,
        MemberCreate(user_id=payload.user_id, account_id=acc.id),
    )
    
    # 3) 为成员添加该用户下所有设备默认控制权限
    device_ids_result = await db.execute(
        select(Device.id).where(Device.user_id == payload.user_id)
    )
    device_ids = [row[0] for row in device_ids_result.all()]
    if device_ids:
        db.add_all([
            MemberDevicePermission(member_id=m.id, device_id=d_id)
            for d_id in device_ids
        ])
        await db.commit()

    return m


class MemberUpdateRequest(BaseModel):
    """更新成员信息（更新 account 数据）

    可选字段：name, gender, phone, email, avatar, password
    注意：提供至少一个字段
    """
    account: str | None = None
    name: str | None = None
    gender: AccountGender | None = None
    phone: constr(pattern=r"^1\d{10}$") | None = None
    email: str | None = None
    avatar: str | None = None
    password: str | None = None


@router.put("/{member_id}", response_model=MemberInDB)
async def update_member_detail(
    member_id: int, 
    payload: MemberUpdateRequest, 
    db: AsyncSession = Depends(get_db),
    guard: dict = Depends(get_current_guard),
):
    # 读取成员
    m = await get_member(db, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="成员不存在")
    # 允许：管理员；该成员本人；或该成员所属用户
    if not (guard.get("role") == "admin" or guard.get("member_id") == member_id):
        ensure_owner_or_admin(m.user_id, guard)

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
        current_acc = await get_account(db, m.account_id)
        current_login = current_acc.account if current_acc else None
        if new_acc != current_login:
            existed = await get_account_by_account_name(db, new_acc)
            if existed and existed.id != m.account_id:
                raise HTTPException(status_code=400, detail="账号已存在")

    # 变更手机号时检重
    if payload.phone is not None:
        from app.crud.account import get_account_by_phone
        existed_phone = await get_account_by_phone(db, payload.phone)
        if existed_phone and existed_phone.id != m.account_id:
            raise HTTPException(status_code=400, detail="手机号已被使用")

    # 规范化并检重邮箱
    norm_email = None
    if payload.email is not None:
        v = (payload.email or "").strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None
        else:
            norm_email = v
            from app.crud.account import get_account_by_email
            existed_email = await get_account_by_email(db, norm_email)
            if existed_email and existed_email.id != m.account_id:
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
        m.account_id,
        AccountUpdate(**updated),
    )

    # 重新返回成员（不展开 account）
    m = await get_member(db, member_id)
    return m


@router.delete("/{member_id}")
async def remove_member(
    member_id: int, 
    db: AsyncSession = Depends(get_db),
    guard: dict = Depends(get_current_guard),
):
    # 先查询成员
    m = await get_member(db, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="成员不存在")
    ensure_owner_or_admin(m.user_id, guard)

    # 先删除 member（会级联删除权限等依赖）
    await delete_member(db, member_id)

    # 再删除其 account（已无外键引用）
    await delete_account(db, m.account_id)
    return {"message": "删除成功"}


