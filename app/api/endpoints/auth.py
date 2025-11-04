from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import re
import asyncio

from app.db.session import get_db
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.account import (
    get_account_by_phone,
    get_account_by_email,
    create_account,
)
from app.crud.user import create_user, get_user_by_account_id
from app.crud.member import create_member, get_member_by_account_id
from app.crud.admin import get_admin_by_account_id
from app.crud.user_operation_log import user_operation_log
from app.models.account import (
    AccountCreate, 
    Account, 
    AccountRole, 
    LoginRequest,
    TokenResponse,
    RegisterRequest
)
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_account, get_current_token
from app.services.websocket_tool import websocket_tool

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """统一登录：支持手机号登录

    说明：
    - phone 为手机号
    - 必须提供密码
    """
    # 按手机号查找
    acc = await get_account_by_phone(db, payload.phone)

    if not acc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 手机号登录：必须提供密码
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号登录需要密码")
    if not acc.password or not verify_password(payload.password, acc.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "account_id": acc.id,
        "role": acc.role,
    }
    # 根据账号角色获取真正的ID和user_id
    user_id = None
    if acc.role == AccountRole.admin:
        admin = await get_admin_by_account_id(db, acc.id)
        if admin:
            extra_claims["id"] = admin.id
            # admin 没有 user_id
    elif acc.role == AccountRole.member:
        member = await get_member_by_account_id(db, acc.id)
        if member:
            extra_claims["id"] = member.id
            user_id = member.user_id
            extra_claims["user_id"] = user_id
    elif acc.role == AccountRole.owner:
        user = await get_user_by_account_id(db, acc.id)
        if user:
            extra_claims["id"] = user.id
            user_id = user.id
            extra_claims["user_id"] = user_id

    token = create_access_token(expires_delta=access_token_expires, extra_claims=extra_claims)

    # 发送family消息通知登录（仅owner和member）
    # 延迟一秒发送，防止客户端的websocket连接还没建立
    if acc.role in [AccountRole.owner, AccountRole.member] and "id" in extra_claims:
        async def send_login_message():
            await asyncio.sleep(1)  # 延迟一秒
            try:
                role_str = acc.role.value if hasattr(acc.role, 'value') else str(acc.role)
                real_id = extra_claims["id"]
                client_id = f"{role_str}_{real_id}"
                
                await websocket_tool.send_family_message(
                    client_id=client_id,
                    message_type="login",
                    data={
                        "senderId": real_id,
                        "senderRole": role_str,
                        "title": "用户登录",
                        "message": f"{acc.nickname or acc.phone} 已登录",
                        "level": "normal"
                    }
                )
            except Exception as e:
                # 发送消息失败不影响登录流程
                print(f"发送登录消息失败: {e}")
        
        # 在后台任务中发送消息，不阻塞登录响应
        asyncio.create_task(send_login_message())

    # 记录登录操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.login,
                description=f"用户登录系统（{acc.nickname or acc.phone}）",
            ),
            account_id=acc.id
        )
    except Exception as e:
        # 记录操作失败不影响登录流程
        print(f"记录登录操作失败: {e}")

    return TokenResponse(
        access_token=token, 
        role=acc.role, 
        account=Account.model_validate(acc),
        id=extra_claims.get("id"),
        user_id=extra_claims.get("user_id")
    )


@router.post("/login/form", response_model=TokenResponse, include_in_schema=False)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """表单登录：兼容 Swagger Authorize（OAuth2 Password flow）

    - username 为手机号
    - password 为明文密码（必填）
    - 忽略 scope 和 client 相关字段
    """
    # 按手机号查找
    acc = await get_account_by_phone(db, form_data.username)

    if not acc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 手机号登录：必须提供密码
    if not form_data.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号登录需要密码")
    if not acc.password or not verify_password(form_data.password, acc.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "account_id": acc.id,
        "role": acc.role,
    }
    # 根据账号角色获取真正的ID和user_id
    user_id = None
    if acc.role == AccountRole.admin:
        admin = await get_admin_by_account_id(db, acc.id)
        if admin:
            extra_claims["id"] = admin.id
            # admin 没有 user_id
    elif acc.role == AccountRole.member:
        member = await get_member_by_account_id(db, acc.id)
        if member:
            extra_claims["id"] = member.id
            user_id = member.user_id
            extra_claims["user_id"] = user_id
    elif acc.role == AccountRole.owner:
        user = await get_user_by_account_id(db, acc.id)
        if user:
            extra_claims["id"] = user.id
            user_id = user.id
            extra_claims["user_id"] = user_id

    token = create_access_token(expires_delta=access_token_expires, extra_claims=extra_claims)

    # 发送family消息通知登录（仅owner和member）
    # 延迟一秒发送，防止客户端的websocket连接还没建立
    if acc.role in [AccountRole.owner, AccountRole.member] and "id" in extra_claims:
        async def send_login_message():
            await asyncio.sleep(1)  # 延迟一秒
            try:
                role_str = acc.role.value if hasattr(acc.role, 'value') else str(acc.role)
                real_id = extra_claims["id"]
                client_id = f"{role_str}_{real_id}"
                
                await websocket_tool.send_family_message(
                    client_id=client_id,
                    message_type="login",
                    data={
                        "senderId": real_id,
                        "senderRole": role_str,
                        "title": "用户登录",
                        "message": f"{acc.nickname or acc.phone} 已登录",
                        "level": "normal"
                    }
                )
            except Exception as e:
                # 发送消息失败不影响登录流程
                print(f"发送登录消息失败: {e}")
        
        # 在后台任务中发送消息，不阻塞登录响应
        asyncio.create_task(send_login_message())

    # 记录登录操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.login,
                description=f"用户登录系统（{acc.nickname or acc.phone}）",
            ),
            account_id=acc.id
        )
    except Exception as e:
        # 记录操作失败不影响登录流程
        print(f"记录登录操作失败: {e}")

    return TokenResponse(
        access_token=token, 
        role=acc.role, 
        account=Account.model_validate(acc),
        id=extra_claims.get("id"),
        user_id=extra_claims.get("user_id")
    )


@router.post("/register", response_model=Account)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册主账号：固定创建 owner 账号并生成对应 user 记录

    必填: phone
    可选: password, nickname, gender, email, avatar
    """
    # 手机号格式校验
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, req.phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    # 手机号唯一性
    phone_exists = await get_account_by_phone(db, req.phone)
    if phone_exists:
        raise HTTPException(status_code=400, detail="手机号已被使用")

    # 规范化并校验邮箱（可选）
    norm_email = (req.email or None)
    if norm_email:
        v = norm_email.strip().lower()
        if v in ("", "string", "null", "undefined"):
            norm_email = None
        else:
            norm_email = v
            email_exists = await get_account_by_email(db, norm_email)
            if email_exists:
                raise HTTPException(status_code=400, detail="邮箱已被使用")

    acc = await create_account(
        db,
        AccountCreate(
            password=req.password,
            phone=req.phone,
            nickname=req.nickname,
            gender=req.gender,  # type: ignore[arg-type]
            email=norm_email,
            avatar=req.avatar,
            role=AccountRole.owner,
        ),
    )

    # 创建 user（owner 对应记录）
    await create_user(db, user=type("UserCreate", (), {"account_id": acc.id})())

    # 记录注册操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.register,
                description=f"用户注册新账号（{acc.nickname or acc.phone}）",
                extra={
                    "registration_type": "owner",
                    "phone": acc.phone,
                    "email": acc.email
                }
            ),
            account_id=acc.id
        )
    except Exception as e:
        # 记录操作失败不影响注册流程
        print(f"记录注册操作失败: {e}")

    return Account.model_validate(acc)


@router.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db),
    current_account: Account = Depends(get_current_account),
    token_info: dict = Depends(get_current_token)
):
    """用户登出"""
    
    # 构建 client_id
    user_id = token_info["id"] if "id" in token_info else None
    role = token_info["role"] if "role" in token_info else None
    if user_id and role:
        client_id = f"{role}_{user_id}"
        
        # 发送family消息通知登出
        try:
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="logout",
                data={
                    "senderId": user_id,
                    "senderRole": role,
                    "title": "用户登出",
                    "message": f"{current_account.nickname or current_account.phone} 已登出",
                    "level": "normal"
                }
            )
        except Exception as e:
            # 发送消息失败不影响登出流程
            print(f"发送登出消息失败: {e}")
    
    # 记录登出操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.logout,
                description=f"用户登出系统（{current_account.nickname or current_account.phone}）",
            ),
            account_id=current_account.id
        )
    except Exception as e:
        # 记录操作失败不影响登出流程
        print(f"记录登出操作失败: {e}")

    return {"message": "登出成功"}



