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
    AdminPasswordReset,
    DepartmentCreate,
    DepartmentOut,
    RefreshTokenRequest,
    RoleOut,
    Token,
    UserAdminUpdate,
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


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only an administrator can list users.")
    stmt = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.department))
        .order_by(User.full_name)
    )
    return (await db.execute(stmt)).scalars().all()


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only an administrator can edit users.")
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles), selectinload(User.department))
    )
    target = (await db.execute(stmt)).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.full_name is not None:
        target.full_name = payload.full_name.strip()
    if "department_id" in payload.model_fields_set:
        if payload.department_id:
            department = await db.get(Department, payload.department_id)
            if not department:
                raise HTTPException(status_code=400, detail="Department not found.")
            target.department_id = department.id
        else:
            target.department_id = None
    if payload.roles is not None:
        requested = payload.roles or ["Staff"]
        roles = (
            await db.execute(select(Role).where(Role.role_name.in_(requested)))
        ).scalars().all()
        found = {role.role_name for role in roles}
        missing = set(requested) - found
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown roles: {', '.join(sorted(missing))}.")
        if "System Admin" in requested and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Only a superuser can grant the System Admin role.")
        target.roles = list(roles)
    if payload.is_active is not None:
        if target.id == current_user.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        target.is_active = payload.is_active

    await db.commit()
    return (
        await db.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles), selectinload(User.department))
        )
    ).scalar_one()


@router.post("/users/{user_id}/password")
async def reset_user_password(
    user_id: str,
    payload: AdminPasswordReset,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only an administrator can reset passwords.")
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.hashed_password = get_password_hash(payload.password)
    await db.commit()
    return {"message": "Password reset."}


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only an administrator can list roles.")
    return (await db.execute(select(Role).order_by(Role.role_name))).scalars().all()


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only an administrator can list departments.")
    return (await db.execute(select(Department).order_by(Department.name))).scalars().all()


@router.post("/departments", response_model=DepartmentOut)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only a superuser can create departments.")
    existing = await db.execute(
        select(Department).where(Department.department_code == payload.department_code.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A department with this code already exists.")
    department = Department(
        department_code=payload.department_code.strip(),
        name=payload.name.strip(),
        faculty=payload.faculty.strip(),
    )
    db.add(department)
    await db.commit()
    await db.refresh(department)
    return department
