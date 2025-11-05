from fastapi import APIRouter, Depends, HTTPException, status, Form
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
    AccountGender,
    LoginRequest,
    TokenResponse,
    RegisterRequest
)
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_account, get_current_token
from app.services.websocket_tool import websocket_tool
from app.services.wechat_service import wechat_service, QRCodeStatus
from fastapi import Query
from typing import Dict
import httpx
import hashlib

router = APIRouter()


async def _generate_login_token_and_notify(
    acc: Account,
    db: AsyncSession,
    login_type: str = "normal",
    extra_log_data: dict = None
) -> TokenResponse:
    """生成登录token并发送通知的共用函数
    
    Args:
        acc: 账户对象
        db: 数据库会话
        login_type: 登录类型（normal, wechat等）
        extra_log_data: 额外的日志数据
    
    Returns:
        TokenResponse: 包含token和用户信息的响应
    """
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
                
                # 根据登录类型设置不同的消息
                if login_type == "wechat":
                    message_text = f"{acc.nickname or acc.phone} 已通过微信登录"
                else:
                    message_text = f"{acc.nickname or acc.phone} 已登录"
                
                await websocket_tool.send_family_message(
                    client_id=client_id,
                    message_type="login",
                    data={
                        "senderId": real_id,
                        "senderRole": role_str,
                        "title": "用户登录",
                        "message": message_text,
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
        log_description = f"用户登录系统（{acc.nickname or acc.phone}）"
        if login_type == "wechat":
            log_description = f"用户通过微信登录系统（{acc.nickname or acc.phone}）"
        
        log_extra = extra_log_data or {}
        
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.login,
                description=log_description,
                extra=log_extra if log_extra else None
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


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """统一登录：支持手机号登录

    说明：
    - phone 为手机号
    - 必须提供密码
    """
    # 验证手机号格式（防止使用openid等非手机号格式登录）
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
    if not acc.password or not verify_password(payload.password, acc.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 使用共用函数生成token并发送通知
    return await _generate_login_token_and_notify(acc, db, login_type="normal")


@router.post("/login/form", response_model=TokenResponse, include_in_schema=False)
async def login_form(
    username: str = Form(...),  # OAuth2标准字段名，实际为手机号
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """表单登录：兼容 Swagger Authorize（OAuth2 Password flow）

    - username 为手机号（OAuth2标准字段名，实际输入手机号）
    - password 为明文密码（必填）
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
    if not acc.password or not verify_password(password, acc.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    # 使用共用函数生成token并发送通知
    return await _generate_login_token_and_notify(acc, db, login_type="normal")


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


@router.get("/login/qrcode")
async def get_wechat_qrcode(db: AsyncSession = Depends(get_db)):
    """获取微信登录二维码
    
    返回二维码URL和scene_id，客户端需要：
    1. 显示二维码图片
    2. 使用scene_id轮询登录状态
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
    code: str = Query(None, description="微信授权码（授权回调时必填）"),
    state: str = Query(None, description="自定义参数，包含scene_id（授权回调时可选）"),
    signature: str = Query(None, description="微信加密签名（验证请求时必填）"),
    timestamp: str = Query(None, description="时间戳（验证请求时必填）"),
    nonce: str = Query(None, description="随机数（验证请求时必填）"),
    echostr: str = Query(None, description="随机字符串（验证请求时必填）"),
    db: AsyncSession = Depends(get_db)
):
    """处理微信回调和验证
    
    此接口同时处理两种请求：
    1. URL验证请求：微信首次配置回调地址时调用（参数：signature, timestamp, nonce, echostr）
    2. 授权回调请求：用户扫码授权后调用（参数：code, state）
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
            
            return {"success": True, "message": "回调处理成功", "openid": openid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"处理回调失败: {str(e)}")


@router.get("/login/check_status")
async def check_wechat_login_status(
    scene_id: str = Query(..., description="场景ID，从qrcode接口获取"),
    db: AsyncSession = Depends(get_db)
):
    """轮询二维码登录状态
    
    客户端需要定期调用此接口检查登录状态。
    当status为confirmed时，返回token信息。
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
            from app.crud.account import get_account_by_unionid
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
                        role=AccountRole.owner,  # 微信登录默认创建owner
                        password=None  # 微信登录不需要密码
                    )
                )
                
                # 将openid保存到unionid字段
                acc.unionid = openid
                await db.commit()
                await db.refresh(acc)
                
                # 创建对应的user记录
                await create_user(db, user=type("UserCreate", (), {"account_id": acc.id})())
            
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
            
            # 使用共用函数生成token并发送通知
            token_response = await _generate_login_token_and_notify(
                acc, 
                db, 
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



