from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    description: Optional[str] = None


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    version_number: int
    file_name: str
    file_size_bytes: int
    mime_type: str
    sha256_checksum: str
    abstract_summary: Optional[str] = None
    extracted_entities: Optional[str] = None
    contains_khmer: bool = False
    created_at: datetime


class DocumentFolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    parent_id: Optional[str] = None
    department_id: str
    created_at: datetime
    document_count: int = 0


class DocumentPermissionOut(BaseModel):
    user_id: str
    full_name: str
    email: str
    permission: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    category: Optional[CategoryOut] = None
    department_id: str
    academic_year: str
    current_version: int
    folder_id: Optional[str] = None
    folder: Optional[DocumentFolderOut] = None
    drive_file_id: Optional[str] = None
    drive_web_link: Optional[str] = None
    is_archived: bool
    is_restricted: bool = False
    permissions: List[DocumentPermissionOut] = []
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[DocumentVersionOut] = None
    versions: List[DocumentVersionOut] = []


class DocumentSearchResponse(BaseModel):
    total: int
    items: List[DocumentOut]
    query_latency_ms: float


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    category_id: Optional[str] = None
    academic_year: Optional[str] = Field(None, min_length=1, max_length=50)
    folder_id: Optional[str] = None
    is_restricted: Optional[bool] = None


class DocumentFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: Optional[str] = None


class DocumentFolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    parent_id: Optional[str] = None


class DocumentShareInput(BaseModel):
    user_id: str
    permission: Literal["view", "edit", "manage"] = "view"


class DocumentArchiveInput(BaseModel):
    is_archived: bool


class GoogleImportInput(BaseModel):
    url: str
    title: Optional[str] = None
    category_id: Optional[str] = None
    folder_id: Optional[str] = None
    academic_year: str = "2026-2027"
