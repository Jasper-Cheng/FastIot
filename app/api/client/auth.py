from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Optional
import re
import hashlib
import httpx

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.account import (
    get_account,
    get_account_by_phone,
    get_account_by_email,
    get_account_by_unionid,
    create_account,
    delete_account,
    update_account,
)
from app.crud.family import get_family
from app.models.account import (
    AccountCreate,
    AccountUpdate,
    Account, 
    AccountRole,
    AccountGender,
    LoginRequest,
    TokenResponse,
    RegisterRequest,
    BindPhoneRequest,
    SetPasswordRequest
)
from app.models.user_operation_log import OperationTypeEnum
from app.api.dependencies import get_current_account, get_current_token
from app.db.session import get_db
from app.core.rsa_crypto import rsa_crypto
from app.services.wechat_service import wechat_service, QRCodeStatus
from app.api.utils import log_operation, log_operation_with_token, extract_token_info

router = APIRouter()

"""
认证授权模块 - Client API

本模块包含：
1. 【App + Web 通用】基础认证接口
   - RSA 公钥获取
   - 登录/注册/登出
   - 用户信息管理
   - 家庭管理
   - 账号注销

2. 【Web 专用】微信登录接口
   - 表单登录（Swagger 调试）
   - 微信二维码登录
   - 微信回调处理
   - 状态轮询
   - 手机号绑定
   - 密码设置

平台识别：通过 token 中的 platform 字段（app/web）
"""


# ============ 共用辅助函数 ============

async def generate_login_token_and_log(
    acc: Account,
    db: AsyncSession,
    platform: str,
    login_type: str = "normal",
    extra_log_data: dict = None
) -> TokenResponse:
    """生成登录token并记录日志的共用函数
    
    Args:
        acc: 账户对象
        db: 数据库会话
        platform: 平台标识（app/web）
        login_type: 登录类型（normal, wechat等）
        extra_log_data: 额外的日志数据
    
    Returns:
        TokenResponse: 包含token和用户信息的响应
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_claims = {
        "account_id": acc.id,
        "role": acc.role,
        "platform": platform,
    }
    
    token = create_access_token(expires_delta=access_token_expires, extra_claims=extra_claims)
    
    # 记录登录操作
    platform_name = "App" if platform == "app" else "Web"
    log_description = f"用户通过{platform_name}登录系统（{acc.nickname or acc.phone}）"
    if login_type == "wechat":
        log_description = f"用户通过微信登录系统（{acc.nickname or acc.phone}）"
    await log_operation(db=db, account_id=acc.id, operation_type=OperationTypeEnum.login, description=log_description, extra=extra_log_data)
    
    return TokenResponse(
        access_token=token,
        role=acc.role,
        account=Account.model_validate(acc)
    )


# ============================================================
# 共同接口 - App + Web 通用
# ============================================================

@router.get("/rsa_public_key")
async def get_rsa_public_key():
    """获取RSA公钥接口
    
    前端需要先调用此接口获取公钥，然后使用公钥加密密码。
    返回公钥（PEM格式），前端可以使用此公钥加密密码。
    """
    try:
        public_key = rsa_crypto.get_public_key()
        return {
            "public_key": public_key,
            "format": "PEM"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取公钥失败: {str(e)}"
        )


async def login_common(
    db: AsyncSession,
    payload: LoginRequest,
    platform: str
) -> TokenResponse:
    """通用登录逻辑
    
    Args:
        db: 数据库会话
        payload: 登录请求数据
        platform: 平台标识（app/web）
    
    Returns:
        TokenResponse: 包含token和用户信息的响应
    """
    # 验证手机号格式
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, payload.phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确")
    
    # 按手机号查找
    acc = await get_account_by_phone(db, payload.phone)

    if not acc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 手机号登录：必须提供密码
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号登录需要密码")
    
    # 解密密码
    try:
        plain_password = rsa_crypto.decrypt(payload.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码解密失败: {str(e)}"
        )
    
    if not acc.password or not verify_password(plain_password, acc.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    
    # 使用共用函数生成token并记录日志
    return await generate_login_token_and_log(acc, db, platform=platform)


async def register_common(
    db: AsyncSession,
    req: RegisterRequest,
    platform: str
) -> TokenResponse:
    """通用注册逻辑
    
    Args:
        db: 数据库会话
        req: 注册请求数据
        platform: 平台标识（app/web）
    
    Returns:
        TokenResponse: 包含token和用户信息的响应
    """
    # 手机号格式校验
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, req.phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    # 手机号唯一性
    phone_exists = await get_account_by_phone(db, req.phone)
    if phone_exists:
        raise HTTPException(status_code=400, detail="手机号已被注册")

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

    # 如果有密码，先解密
    decrypted_password = None
    if req.password:
        try:
            decrypted_password = rsa_crypto.decrypt(req.password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码解密失败: {str(e)}"
            )
    
    acc = await create_account(
        db,
        AccountCreate(
            password=decrypted_password,
            phone=req.phone,
            nickname=req.nickname,
            gender=req.gender,  # type: ignore[arg-type]
            email=norm_email,
            avatar=req.avatar,
            role=AccountRole.user,
        ),
    )
    
    # 记录注册操作
    platform_name = "App" if platform == "app" else "Web"
    await log_operation(
            db=db,
        account_id=acc.id,
                operation_type=OperationTypeEnum.register,
                description=f"用户通过{platform_name}注册新账号（{acc.nickname or acc.phone}）",
                extra={
                    "registration_type": "user",
                    "phone": acc.phone,
                    "email": acc.email,
                    "platform": platform
                }
        )

    # 注册成功后自动登录
    return await generate_login_token_and_log(acc, db, platform=platform)


# ============================================================
# 通用登录注册接口 - App + Web 通用
# ============================================================

@router.post("/login", response_model=TokenResponse)
async def login(
    db: AsyncSession = Depends(get_db),
    payload: LoginRequest = Body(...),
    platform: str = Query("app", description="平台标识：app 或 web")
):
    """【App + Web 通用】用户登录
    
    参数：
    - phone: 手机号（必填）
    - password: 密码（RSA加密的Base64字符串）
    - platform: 平台标识（app/web，默认app）
    
    注意：密码需要使用RSA公钥加密后传输
    """
    return await login_common(db, payload, platform)


@router.post("/register", response_model=TokenResponse)
async def register(
    db: AsyncSession = Depends(get_db),
    req: RegisterRequest = Body(...),
    platform: str = Query("app", description="平台标识：app 或 web")
):
    """【App + Web 通用】用户注册
    
    参数：
    - phone: 手机号（必填）
    - password: 密码（RSA加密的Base64字符串，必填）
    - nickname: 昵称（可选）
    - gender: 性别（可选：male/female/other）
    - email: 邮箱（可选）
    - avatar: 头像URL（可选）
    - platform: 平台标识（app/web，默认app）
    
    注意：
    - 密码需要使用RSA公钥加密后传输
    - 注册成功后自动登录，返回token
    """
    return await register_common(db, req, platform)


# ============================================================
# Web 平台专用接口
# ============================================================

@router.post("/login/form", response_model=TokenResponse, include_in_schema=False)
async def login_form(
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),  # OAuth2标准字段名，实际为手机号
    password: str = Form(...)
):
    """【Web 专用】表单登录：兼容 Swagger Authorize（OAuth2 Password flow）

    - username 为手机号（OAuth2标准字段名，实际输入手机号）
    - password 为明文密码（必填，不进行解密，直接用于验证）
    - 仅用于 Web 端 Swagger 调试
    """
    # 按手机号查找（username 实际为手机号）
    phone = username
    
    # 验证手机号格式（防止使用openid等非手机号格式登录）
    phone_pattern = r"^1\d{10}$"
    if not re.match(phone_pattern, phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确")
    
    acc = await get_account_by_phone(db, phone)

    if not acc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    
    # 手机号登录：必须提供密码
    if not password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号登录需要密码")
    
    # login_form 中使用明文密码，不进行解密（用于Swagger测试）
    if not acc.password or not verify_password(password, acc.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 使用共用函数生成token并记录日志（web平台，因为Swagger通常在web端使用）
    return await generate_login_token_and_log(acc, db, platform="web")


@router.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account)
):
    """用户登出"""
    
    # 记录登出操作
    _, platform, _ = extract_token_info(token_info)
    platform_name = "App" if platform == "app" else "Web"
    await log_operation(
            db=db,
        account_id=current_account.id,
                operation_type=OperationTypeEnum.logout,
                description=f"用户从{platform_name}登出系统（{current_account.nickname or current_account.phone}）",
                extra={"platform": platform}
        )

    return {"message": "登出成功"}


@router.get("/profile", response_model=Account)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_account: Account = Depends(get_current_account)
):
    """获取当前用户信息"""
    return Account.model_validate(current_account)


@router.patch("/profile", response_model=Account)
async def update_profile(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account),
    account_update: AccountUpdate = Body(...)
):
    """更新当前用户信息
    
    接收一个对象，只更新提供的字段：
    - nickname: 昵称
    - gender: 性别 (male/female/other)
    - email: 邮箱
    - phone: 手机号
    - avatar: 头像URL
    - password: 密码（RSA加密的Base64字符串，会自动解密）
    """
    # 如果提供了密码，需要先解密
    update_data = account_update.dict(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        try:
            # RSA解密密码
            plain_password = rsa_crypto.decrypt(update_data["password"])
            # 验证密码长度
            if len(plain_password) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密码长度至少6位"
                )
            update_data["password"] = plain_password
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码解密失败: {str(e)}"
            )
    
    # 如果提供了手机号，检查是否已被其他账号使用
    if "phone" in update_data and update_data["phone"]:
        existing_account = await get_account_by_phone(db, update_data["phone"])
        if existing_account and existing_account.id != current_account.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已被其他账号使用"
            )
    
    # 如果提供了邮箱，检查是否已被其他账号使用
    if "email" in update_data and update_data["email"]:
        existing_account = await get_account_by_email(db, update_data["email"])
        if existing_account and existing_account.id != current_account.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被其他账号使用"
            )
    
    # 创建更新对象
    update_obj = AccountUpdate(**update_data)
    
    # 更新账号信息
    updated_account = await update_account(db, current_account.id, update_obj)
    
    if not updated_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    # 记录操作日志
    _, platform, _ = extract_token_info(token_info)
    platform_name = "App" if platform == "app" else "Web"
    await log_operation(
            db=db,
        account_id=current_account.id,
                operation_type=OperationTypeEnum.account_update,
                description=f"通过{platform_name}更新用户信息",
                extra={
                    "updated_fields": list(update_data.keys()),
                    "platform": platform
                }
        )
    
    # TODO: 消息通知功能待重构
    
    return Account.model_validate(updated_account)


@router.get("/current-family")
async def get_current_family(
    db: AsyncSession = Depends(get_db),
    current_account: Account = Depends(get_current_account)
):
    """获取当前家庭信息"""
    if not current_account.current_family_id:
        raise HTTPException(status_code=404, detail="未设置当前家庭")
    
    family = await get_family(db, current_account.current_family_id)
    if not family:
        raise HTTPException(status_code=404, detail="当前家庭不存在")
    
    return {
        "id": family.id,
        "name": family.name,
        "avatar": family.avatar,
        "description": family.description,
        "invite_code": family.invite_code,
        "created_at": family.created_at,
        "updated_at": family.updated_at
    }


@router.patch("/current-family", response_model=Account)
async def update_current_family(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account),
    family_id: Optional[int] = Query(None, description="家庭ID，如果提供则设置为当前家庭；如果为None则设置为个人使用")
):
    """更新当前使用的家庭ID
    
    - 如果提供 family_id：验证用户是否是家庭成员，然后设置为当前家庭
    - 如果 family_id 为 None：设置为个人使用（current_family_id = NULL）
    """
    account_id, _, _ = extract_token_info(token_info)
    
    # 如果提供了 family_id，验证用户是否是家庭成员
    if family_id is not None:
        from app.crud.family_member import get_family_member_by_family_and_account
        
        # 验证家庭是否存在
        family = await get_family(db, family_id)
        if not family:
            raise HTTPException(status_code=404, detail="家庭不存在")
        
        # 验证用户是否是家庭成员
        family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
        if not family_member:
            raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    # 直接更新 current_family_id
    current_account.current_family_id = family_id
    await db.commit()
    await db.refresh(current_account)
    
    return current_account


@router.get("/login/qrcode")
async def get_wechat_qrcode(db: AsyncSession = Depends(get_db)):
    """【Web 专用】获取微信登录二维码
    
    返回二维码URL和scene_id，客户端需要：
    1. 显示二维码图片
    2. 使用scene_id轮询登录状态
    
    注意：仅 Web 平台支持微信扫码登录
    """
    try:
        result = await wechat_service.create_qrcode()
        return {
            "qrcode_url": result["qrcode_url"],
            "scene_id": result["scene_id"]
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"生成二维码失败: {str(e)}")


@router.get("/login/wechat_callback")
async def wechat_callback(
    db: AsyncSession = Depends(get_db),
    code: str = Query(None, description="微信授权码（授权回调时必填）"),
    state: str = Query(None, description="自定义参数，包含scene_id（授权回调时可选）"),
    signature: str = Query(None, description="微信加密签名（验证请求时必填）"),
    timestamp: str = Query(None, description="时间戳（验证请求时必填）"),
    nonce: str = Query(None, description="随机数（验证请求时必填）"),
    echostr: str = Query(None, description="随机字符串（验证请求时必填）")
):
    """【Web 专用】处理微信回调和验证
    
    此接口同时处理两种请求：
    1. URL验证请求：微信首次配置回调地址时调用（参数：signature, timestamp, nonce, echostr）
    2. 授权回调请求：用户扫码授权后调用（参数：code, state）
    
    注意：仅 Web 平台支持微信扫码登录
    """
    # 判断是否为验证请求
    if signature and timestamp and nonce and echostr:
        # 这是验证请求
        if not settings.WECHAT_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="微信Token未配置"
            )
        
        # 将token、timestamp、nonce三个参数进行字典序排序
        tmp_arr = [settings.WECHAT_TOKEN, timestamp, nonce]
        tmp_arr.sort()
        
        # 将三个参数字符串拼接成一个字符串
        tmp_str = ''.join(tmp_arr)
        
        # 进行sha1加密
        hash_str = hashlib.sha1(tmp_str.encode('utf-8')).hexdigest()
        
        # 与signature对比，标识该请求来源于微信
        if hash_str == signature:
            # 验证成功，返回echostr（必须是纯文本，不是JSON）
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=echostr)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="签名验证失败"
            )
    
    # 否则是授权回调请求
    try:
        # 从state中提取scene_id
        scene_id = state if state else None
        
        if not code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少授权码code")
        
        # 通过code获取access_token和openid
        url = "https://api.weixin.qq.com/sns/oauth2/access_token"
        params = {
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
            "code": code,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
            
            # 检查错误
            if "errcode" in data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"微信授权失败: {data.get('errmsg', '未知错误')}"
                )
            
            openid = data.get("openid")
            if not openid:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法获取openid")
            
            # 获取用户信息（使用网页授权接口）
            access_token = data.get("access_token")
            user_info = await wechat_service.get_user_info_by_openid(openid, access_token, use_sns=True)
            
            # 如果有scene_id，更新二维码状态
            if scene_id:
                success = await wechat_service.handle_wechat_callback(scene_id, openid, user_info)
                if not success:
                    # 二维码可能已过期，但不影响登录流程，只记录警告
                    print(f"警告: 无法更新二维码状态，scene_id可能已过期: {scene_id}")
            
            return {"success": True, "message": "very good!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"处理回调失败: {str(e)}")


@router.get("/login/check_status")
async def check_wechat_login_status(
    db: AsyncSession = Depends(get_db),
    scene_id: str = Query(..., description="场景ID，从qrcode接口获取")
):
    """【Web 专用】轮询二维码登录状态
    
    客户端需要定期调用此接口检查登录状态。
    当status为confirmed时，返回token信息。
    
    注意：仅 Web 平台支持微信扫码登录
    """
    try:
        status_info = wechat_service.get_qrcode_status(scene_id)
        status_value = status_info.get("status")
        
        if status_value == QRCodeStatus.EXPIRED:
            return {
                "status": QRCodeStatus.EXPIRED,
                "message": "二维码已过期"
            }
        
        if status_value == QRCodeStatus.CONFIRMED:
            # 登录成功，需要根据openid查找或创建账户
            openid = status_info.get("openid")
            user_info = status_info.get("user_info", {})
            
            if not openid:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺少openid")
            
            # 使用openid作为unionid查询账户（openid保存在unionid字段）
            acc = await get_account_by_unionid(db, openid)
            
            # 如果找不到账户，创建新账户
            if not acc:
                # 创建新账户，使用openid作为phone（满足唯一性约束，但格式不是真实手机号）
                nickname = user_info.get("nickname") or "微信用户"
                avatar = user_info.get("headimgurl")
                gender_str = user_info.get("sex", 0)  # 1:男, 2:女, 0:未知
                gender = AccountGender.male if gender_str == 1 else (AccountGender.female if gender_str == 2 else AccountGender.other)
                
                acc = await create_account(
                    db,
                    AccountCreate(
                        phone=openid,  # 使用openid作为phone，满足唯一性约束
                        nickname=nickname,
                        avatar=avatar,
                        gender=gender,
                        role=AccountRole.user,  # 微信登录默认创建user
                        password=None  # 微信登录不需要密码
                    )
                )
                
                # 将openid保存到unionid字段
                acc.unionid = openid
                await db.commit()
                await db.refresh(acc)
            
            # 判断手机号是否为真实手机号（格式：1开头的11位数字）
            phone_pattern = r"^1\d{10}$"
            is_real_phone = bool(re.match(phone_pattern, acc.phone))
            
            # 如果没有真实手机号，返回需要绑定的响应
            if not is_real_phone:
                return {
                    "status": QRCodeStatus.CONFIRMED,
                    "need_bind_phone": True,
                    "scene_id": scene_id,
                    "message": "需要绑定手机号"
                }
            
            # 使用共用函数生成token并记录日志（web平台）
            token_response = await generate_login_token_and_log(
                acc, 
                db, 
                platform="web",
                login_type="wechat",
                extra_log_data={
                    "login_type": "wechat",
                    "openid": openid,
                    "unionid": acc.unionid
                }
            )
            
            return {
                "status": QRCodeStatus.CONFIRMED,
                "token": token_response
            }
        
        # 其他状态（waiting, scanned）
        return {
            "status": status_value,
            "message": "等待扫码" if status_value == QRCodeStatus.WAITING else "已扫码，等待确认"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检查状态失败: {str(e)}")


@router.post("/login/bind_phone", response_model=TokenResponse)
async def bind_phone(
    db: AsyncSession = Depends(get_db),
    payload: BindPhoneRequest = Body(...)
):
    """【Web 专用】绑定手机号接口
    
    微信登录后，如果用户没有真实手机号，需要调用此接口绑定手机号。
    参数：
    - scene_id: 场景ID（从check_status接口获取）
    - phone: 手机号（必填，格式：1开头的11位数字）
    
    注意：仅用于 Web 平台微信登录流程
    """
    try:
        # 验证手机号格式
        phone_pattern = r"^1\d{10}$"
        if not re.match(phone_pattern, payload.phone):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确")
        
        # 通过scene_id直接获取openid（不判断状态）
        openid = None
        if payload.scene_id in wechat_service.qrcode_storage:
            qrcode_info = wechat_service.qrcode_storage[payload.scene_id]
            openid = qrcode_info.get("openid")
        
        if not openid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="无法获取openid，请重新扫码"
            )
        
        # 使用openid作为unionid查询账户
        acc = await get_account_by_unionid(db, openid)
        
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="账户不存在，请重新扫码登录"
            )
        
        # 检查手机号是否已被使用
        existing = await get_account_by_phone(db, payload.phone)
        if existing and existing.id != acc.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="该手机号已被使用"
            )
        
        # 检查账户是否已经有真实手机号
        is_real_phone = bool(re.match(phone_pattern, acc.phone))
        if is_real_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="账户已绑定手机号，无需重复绑定"
            )
        
        # 更新手机号
        acc = await update_account(
            db,
            acc.id,
            AccountUpdate(phone=payload.phone)
        )
        
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="更新手机号失败"
            )
        
        # 使用共用函数生成token并记录日志（web平台）
        token_response = await generate_login_token_and_log(
            acc,
            db,
            platform="web",
            login_type="wechat",
            extra_log_data={
                "login_type": "wechat",
                "openid": openid,
                "unionid": acc.unionid,
                "action": "bind_phone"
            }
        )
        
        return token_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"绑定手机号失败: {str(e)}"
        )


@router.post("/set_password")
async def set_password(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    payload: SetPasswordRequest = Body(...)
):
    """【Web 专用】设置密码接口
    
    为当前登录用户设置密码。
    参数：
    - password: 新密码（必填，RSA 加密）
    
    注意：主要用于 Web 平台微信登录后设置密码
    """
    # 解密密码
    try:
        plain_password = rsa_crypto.decrypt(payload.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码解密失败: {str(e)}"
        )
    
    # 验证密码长度（可根据需求调整）
    if len(plain_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="密码长度至少6位"
        )
    
    account_id, _, _ = extract_token_info(token_info)
    
    # 获取账户信息（用于日志记录）
    acc = await get_account(db, account_id)
    if not acc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="账户不存在"
        )
    
    # 更新密码（使用解密后的明文密码）
    updated_account = await update_account(
        db,
        account_id,
        AccountUpdate(password=plain_password)
    )
    
    if not updated_account:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="设置密码失败"
        )
    
    # 记录操作日志
    _, platform, _ = extract_token_info(token_info)
    await log_operation(
        db=db,
        account_id=account_id,
        operation_type=OperationTypeEnum.user_update,
        description=f"用户设置密码（{acc.nickname or acc.phone}）",
        extra={
            "action": "set_password",
            "platform": platform
        }
    )
    
    return {"message": "密码设置成功"}


@router.delete("/account")
async def delete_account_endpoint(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    current_account: Account = Depends(get_current_account)
):
    """注销账号（删除当前登录用户的账号）
    
    不需要接收参数，会自动删除当前登录用户的账号。
    删除前会：
    1. 如果账号是家庭创建者，自动删除这些家庭（会级联删除家庭成员和设备关联）
    2. 从所有家庭中移除设备关联（family_device 表）
    3. 更新设备状态为 unbound
    4. 记录操作日志
    5. 删除账号（会级联删除家庭成员关系、签到记录、积分记录、反馈、操作日志等）
    
    注意：
    - device.account_id 会在删除账号时自动设为 NULL (ON DELETE SET NULL)
    - family_member 记录会在删除账号时自动删除（ON DELETE CASCADE）
    """
    account_id, platform, _ = extract_token_info(token_info)
    platform_name = "App" if platform == "app" else "Web"
    
    # 如果账号是任何家庭的创建者，先删除这些家庭
    from app.crud.family_member import get_family_members_by_account
    from app.models.family_member import FamilyMemberRole
    from app.crud.family import get_family, delete_family
    
    family_members = await get_family_members_by_account(db, account_id)
    creator_families = [fm for fm in family_members if fm.role == FamilyMemberRole.creator]
    
    # 删除所有创建的家庭
    deleted_families = []  # 记录成功删除的家庭信息
    for fm in creator_families:
        family = await get_family(db, fm.family_id)
        if family:
            # 保存家庭信息用于后续日志
            family_id = family.id
            family_name = family.name
            
            # 先删除家庭（会级联删除家庭成员和设备关联）
            success = await delete_family(db, fm.family_id)
            
            # 删除成功后保存家庭信息
            if success:
                deleted_families.append({
                    "familyId": family_id,
                    "familyName": family_name
                })
    
    # 如果删除了家庭，记录一条日志
    if deleted_families:
        try:
            if len(deleted_families) == 1:
                description = f"通过{platform_name}删除家庭: {deleted_families[0]['familyName']}（账号注销时自动删除）"
                extra = {
                    "family_id": deleted_families[0]["familyId"],
                    "family_name": deleted_families[0]["familyName"],
                    "reason": "account_deletion",
                    "platform": platform
                }
            else:
                family_names = [f["familyName"] for f in deleted_families]
                description = f"通过{platform_name}删除 {len(deleted_families)} 个家庭（账号注销时自动删除）: {', '.join(family_names)}"
                extra = {
                    "families": deleted_families,
                    "count": len(deleted_families),
                    "reason": "account_deletion",
                    "platform": platform
                }
            
            await log_operation(
                db=db,
                account_id=account_id,
                    operation_type=OperationTypeEnum.family_delete,
                    description=description,
                    extra=extra
            )
        except Exception as e:
            print(f"记录删除家庭操作日志失败: {e}")
        
        # TODO: 消息通知功能待重构
    
    # 记录操作日志（在删除前记录，因为删除后日志也会被级联删除）
    await log_operation(
            db=db,
        account_id=account_id,
                operation_type=OperationTypeEnum.account_delete,
                description=f"通过{platform_name}注销账号：{current_account.nickname or current_account.phone}",
                extra={
                    "account_id": account_id,
                    "nickname": current_account.nickname,
                    "phone": current_account.phone,
                    "platform": platform
                }
        )
    
    # 处理设备：从所有家庭中移除，并更新状态
    from app.crud.device import get_devices_by_account
    from app.crud.family_device import delete_all_family_devices_by_device
    from app.models.device import DeviceStatus
    
    devices = await get_devices_by_account(db, account_id)
    for device in devices:
        # 从所有家庭中移除设备
        await delete_all_family_devices_by_device(db, device.id)
        # 更新设备状态为 unbound
        device.status = DeviceStatus.unbound
    
    await db.commit()
    
    # 删除账号
    from app.crud.account import delete_account as delete_account_crud
    success = await delete_account_crud(db, account_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    await db.commit()
    
    return {"message": "账号已成功注销"}

