import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.user import Department, Role, User
from app.schemas.user import (
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_FAILURES = 5
_login_failures: dict[str, list[float]] = {}


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _is_admin(user: User) -> bool:
    return user.is_superuser or any(role.role_name == "System Admin" for role in user.roles)


def _login_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{email}"


def _check_login_rate_limit(key: str) -> None:
    now = time.time()
    attempts = [stamp for stamp in _login_failures.get(key, []) if now - stamp < _LOGIN_WINDOW_SECONDS]
    _login_failures[key] = attempts
    if len(attempts) >= _LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Wait a few minutes and try again.",
            headers={"Retry-After": str(_LOGIN_WINDOW_SECONDS)},
        )


def _record_login_failure(key: str) -> None:
    _login_failures.setdefault(key, []).append(time.time())


def _clear_login_failures(key: str) -> None:
    _login_failures.pop(key, None)


@router.post("/register", response_model=UserOut)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator can create user accounts.",
        )

    email = _normalize_email(str(user_in.email))
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A user with this email address already exists.")

    requested_roles = user_in.roles or ["Staff"]
    stmt = select(Role).where(Role.role_name.in_(requested_roles))
    assigned_roles = (await db.execute(stmt)).scalars().all()
    found_roles = {role.role_name for role in assigned_roles}
    missing_roles = set(requested_roles) - found_roles
    if missing_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown roles: {', '.join(sorted(missing_roles))}.",
        )
    if "System Admin" in requested_roles and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superuser can grant the System Admin role.",
        )

    if user_in.department_id:
        department = await db.get(Department, user_in.department_id)
        if not department:
            raise HTTPException(status_code=400, detail="The selected department does not exist.")

    new_user = User(
        email=email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        student_or_staff_id=user_in.student_or_staff_id,
        department_id=user_in.department_id,
        is_active=True,
        roles=list(assigned_roles),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    stmt = (
        select(User)
        .where(User.id == new_user.id)
        .options(selectinload(User.roles), selectinload(User.department))
    )
    return (await db.execute(stmt)).scalar_one()


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    email = _normalize_email(form_data.username)
    rate_key = _login_key(request, email)
    _check_login_rate_limit(rate_key)

    stmt = (
        select(User)
        .where(User.email == email)
        .options(selectinload(User.roles), selectinload(User.department))
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        _record_login_failure(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is deactivated. Contact an administrator.",
        )

    _clear_login_failures(rate_key)
    roles = [role.role_name for role in user.roles]
    return {
        "access_token": create_access_token(subject=user.id, roles=roles),
        "token_type": "bearer",
        "refresh_token": create_refresh_token(subject=user.id),
        "user": user,
    }


@router.post("/refresh", response_model=Token)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session has expired. Sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        decoded = jwt.decode(
            payload.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise credentials_exception from exc

    if decoded.get("type") != "refresh":
        raise credentials_exception
    user_id = decoded.get("sub")
    if not user_id:
        raise credentials_exception

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles), selectinload(User.department))
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    roles = [role.role_name for role in user.roles]
    return {
        "access_token": create_access_token(subject=user.id, roles=roles),
        "token_type": "bearer",
        "refresh_token": create_refresh_token(subject=user.id),
        "user": user,
    }


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(current_user: User = Depends(get_current_user)) -> Any:
    return current_user
