from typing import List, Optional
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


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    category: Optional[CategoryOut] = None
    department_id: str
    academic_year: str
    current_version: int
    drive_file_id: Optional[str] = None
    drive_web_link: Optional[str] = None
    is_archived: bool
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


class DocumentArchiveInput(BaseModel):
    is_archived: bool


class GoogleImportInput(BaseModel):
    url: str
    title: Optional[str] = None
    category_id: Optional[str] = None
    academic_year: str = "2026-2027"
