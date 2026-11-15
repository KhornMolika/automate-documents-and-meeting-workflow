from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.api.deps import get_current_user
from app.models.user import User, Role, Department
from app.schemas.user import UserCreate, UserOut, Token, UserLogin

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Check if user already exists
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="A user with this email address already exists."
        )

    # Resolve roles
    stmt = select(Role).where(Role.role_name.in_(user_in.roles or ["Staff"]))
    role_res = await db.execute(stmt)
    assigned_roles = role_res.scalars().all()

    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        student_or_staff_id=user_in.student_or_staff_id,
        department_id=user_in.department_id,
        is_active=True,
        roles=list(assigned_roles)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Re-fetch with relationships loaded
    stmt = select(User).where(User.id == new_user.id).options(selectinload(User.roles), selectinload(User.department))
    result = await db.execute(stmt)
    return result.scalar_one()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Any:
    stmt = select(User).where(User.email == form_data.username).options(selectinload(User.roles), selectinload(User.department))
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated")

    roles = [r.role_name for r in user.roles]
    access_token = create_access_token(subject=user.id, roles=roles)
    refresh_token = create_refresh_token(subject=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "user": user
    }


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
) -> Any:
    return current_user
