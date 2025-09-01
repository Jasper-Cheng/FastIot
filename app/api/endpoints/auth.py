from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.crud.user import create_user, authenticate_user, get_user_by_username, get_user_by_email
from app.models.token import Token
from app.models.user import UserCreate, User, UserRole

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class CurrentUserClaims(BaseModel):
    id: int
    username: str
    role: UserRole


async def get_current_user_claims(
    token: str = Depends(oauth2_scheme)
) -> CurrentUserClaims:
    """从JWT直接解析当前用户信息（不查数据库）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: int | None = payload.get("user_id")
        username: str | None = payload.get("username")
        role_raw = payload.get("role")
        if user_id is None or not username or role_raw is None:
            raise credentials_exception
        return CurrentUserClaims(id=int(user_id), username=username, role=UserRole(role_raw))
    except JWTError:
        raise credentials_exception


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    db_user = await get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # 检查邮箱是否已存在
    db_user = await get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 创建新用户
    return await create_user(db=db, user=user)


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """用户登录"""
    print(f"🔐 [LOGIN] 登录尝试: {form_data.username}")

    # 验证用户凭据
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        print(f"❌ [LOGIN] 登录失败: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 生成访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        expires_delta=access_token_expires,
        extra_claims={"username": user.username, "user_id": user.id, "role": user.role}
    )

    print(f"✅ [LOGIN] 登录成功: {form_data.username}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """刷新访问令牌（使用当前DB用户信息）"""
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        expires_delta=access_token_expires,
        extra_claims={"user_id": current_user.id, "username": current_user.username, "role": current_user.role}
    )

    return {"access_token": access_token, "token_type": "bearer"}
