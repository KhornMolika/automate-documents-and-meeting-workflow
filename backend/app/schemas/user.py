from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


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
    password: str
    roles: Optional[List[str]] = ["Staff"]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    is_active: bool
    roles: List[RoleOut] = []
    department: Optional[DepartmentOut] = None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    user: UserOut


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    roles: List[str] = []
    type: Optional[str] = None
