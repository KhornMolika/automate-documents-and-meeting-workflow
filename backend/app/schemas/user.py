from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role_name: str
    description: Optional[str] = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    department_code: str
    name: str
    faculty: str


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    student_or_staff_id: Optional[str] = None
    department_id: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    roles: Optional[List[str]] = ["Staff"]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    is_active: bool
    roles: List[RoleOut] = []
    department: Optional[DepartmentOut] = None
    created_at: datetime


class UserAdminUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    department_id: Optional[str] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AdminPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class DepartmentCreate(BaseModel):
    department_code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    faculty: str = Field(min_length=1, max_length=255)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    user: UserOut


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    roles: List[str] = []
    type: Optional[str] = None
