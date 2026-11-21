import io
import json
import os
import re
import time
from pathlib import Path
from typing import Any, List, Literal, Optional
from urllib.parse import unquote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.datastructures import Headers

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document, DocumentCategory, DocumentVersion
from app.models.user import User
from app.schemas.document import (
    CategoryOut,
    DocumentArchiveInput,
    DocumentOut,
    DocumentSearchResponse,
    DocumentUpdate,
    GoogleImportInput,
)
from app.services.extractor import compute_sha256, extract_text
from app.services.llm_service import AIServiceUnavailable, llm_service

router = APIRouter(prefix="/documents", tags=["Document Management"])

_GOOGLE_DOC_RE = re.compile(r"https?://docs\.google\.com/document/d/([A-Za-z0-9_-]+)")
_GOOGLE_SHEET_RE = re.compile(r"https?://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)")
_GOOGLE_SLIDE_RE = re.compile(r"https?://docs\.google\.com/presentation/d/([A-Za-z0-9_-]+)")
_GOOGLE_DRIVE_FILE_RE = re.compile(r"https?://drive\.google\.com/file/d/([A-Za-z0-9_-]+)")
_GOOGLE_DRIVE_OPEN_RE = re.compile(r"https?://drive\.google\.com/open\?id=([A-Za-z0-9_-]+)")


def _can_access_document(document: Document, user: User) -> bool:
    if user.is_superuser or not user.department_id:
        return True
    return document.department_id == user.department_id


def _can_manage_document(document: Document, user: User) -> bool:
    if user.is_superuser or document.owner_id == user.id:
        return True
    if not _can_access_document(document, user):
        return False
    return any(role.role_name in {"System Admin", "Department Admin"} for role in user.roles)


def _document_options():
    return (
        selectinload(Document.category),
        selectinload(Document.versions),
    )


def _attach_latest(document: Document) -> Document:
    document.latest_version = document.versions[0] if document.versions else None
    return document


async def _load_document(db: AsyncSession, document_id: str) -> Document:
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(*_document_options())
        .execution_options(populate_existing=True)
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return _attach_latest(document)


def _validate_document_file(filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in settings.ALLOWED_EXTENSIONS:
        allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=400,
            detail=f"File extension '.{extension}' is not supported. Allowed: {allowed}",
        )
    return extension


async def _read_limited_upload(upload: UploadFile) -> bytes:
    data = await upload.read()
    if len(data) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )
    return data


def _google_export_target(url: str) -> tuple[str, str, str]:
    """Return (download_url, filename, mime_type) for a supported Google link."""
    value = url.strip()
    document = _GOOGLE_DOC_RE.search(value)
    if document:
        file_id = document.group(1)
        return (
            f"https://docs.google.com/document/d/{file_id}/export?format=docx",
            f"google-doc-{file_id[:8]}.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    sheet = _GOOGLE_SHEET_RE.search(value)
    if sheet:
        file_id = sheet.group(1)
        return (
            f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx",
            f"google-sheet-{file_id[:8]}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    slide = _GOOGLE_SLIDE_RE.search(value)
    if slide:
        file_id = slide.group(1)
        return (
            f"https://docs.google.com/presentation/d/{file_id}/export?format=pdf",
            f"google-slides-{file_id[:8]}.pdf",
            "application/pdf",
        )
    drive_file = _GOOGLE_DRIVE_FILE_RE.search(value) or _GOOGLE_DRIVE_OPEN_RE.search(value)
    if drive_file:
        file_id = drive_file.group(1)
        return (
            f"https://drive.google.com/uc?export=download&id={file_id}",
            f"google-drive-{file_id[:8]}.bin",
            "application/octet-stream",
        )
    raise HTTPException(
        status_code=400,
        detail=(
            "Use a Google Docs, Google Sheets, Google Slides, or Google Drive file link. "
            "Share pages that require sign-in are not supported."
        ),
    )


def _imported_filename(content_type: str, content_disposition: str | None, fallback: str) -> str:
    if content_disposition:
        match = re.search(r'filename\*?=(?:UTF-8\'\'|"?)([^";]+)', content_disposition, re.I)
        if match:
            candidate = unquote(match.group(1)).strip().strip('"')
            if candidate:
                return Path(candidate).name
    suffix = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "text/csv": ".csv",
        "application/vnd.ms-excel": ".xls",
    }.get(content_type.split(";")[0].strip().lower())
    return fallback if not suffix or fallback.endswith(suffix) else f"{fallback}{suffix}"


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    academic_year: str = Form("2024-2025"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    # 1. Validate file extension
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '.{ext}' is not supported. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    # 2. Compute SHA-256
    checksum = compute_sha256(file_bytes)

    # 3. Check for duplicates in the same department
    dept_id = current_user.department_id
    if not dept_id:
        raise HTTPException(
            status_code=400,
            detail="Your account is not assigned to a department. Contact an administrator.",
        )
    dup_stmt = (
        select(DocumentVersion)
        .join(Document)
        .where(Document.department_id == dept_id, DocumentVersion.sha256_checksum == checksum)
    )
    dup_res = await db.execute(dup_stmt)
    existing_version = dup_res.scalar_one_or_none()
    if existing_version:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate document detected! This file was already uploaded under Document ID {existing_version.document_id}."
        )

    # 4. Extract Text
    extracted_text = extract_text(file_bytes, file.filename)

    # 5. Document title
    doc_title = title or file.filename.rsplit(".", 1)[0].replace("_", " ").title()

    # 6. AI summarization is opt-in so uploads stay fast (local models can be slow).
    ai_result = {}
    if settings.AUTO_SUMMARIZE_ON_UPLOAD:
        try:
            ai_result = await llm_service.summarize_document(doc_title, extracted_text)
        except AIServiceUnavailable:
            # The document is still saved; the UI can retry summarization later.
            ai_result = {}
    abstract_summary = ai_result.get("abstract_summary")
    entities_json = json.dumps(ai_result.get("entities")) if ai_result.get("entities") is not None else None

    # 7. Store file locally (or cloud drive pointer)
    os.makedirs("./uploads", exist_ok=True)
    local_path = f"./uploads/{checksum}_{file.filename}"
    with open(local_path, "wb") as f:
        f.write(file_bytes)

    # 8. Persist Document & Version in Database
    new_doc = Document(
        title=doc_title,
        category_id=category_id,
        department_id=dept_id,
        owner_id=current_user.id,
        academic_year=academic_year,
        current_version=1,
    )
    db.add(new_doc)
    await db.flush()

    new_version = DocumentVersion(
        document_id=new_doc.id,
        version_number=1,
        file_name=file.filename,
        file_path=local_path,
        file_size_bytes=file_size,
        mime_type=file.content_type or f"application/{ext}",
        sha256_checksum=checksum,
        extracted_text=extracted_text,
        abstract_summary=abstract_summary,
        extracted_entities=entities_json,
        uploaded_by=current_user.id,
    )
    db.add(new_version)
    await db.commit()

    # Return refreshed document
    stmt = (
        select(Document)
        .where(Document.id == new_doc.id)
        .options(
            selectinload(Document.category),
            selectinload(Document.versions),
        )
    )
    res = await db.execute(stmt)
    created = res.scalar_one()
    # attach latest_version
    created.latest_version = new_version
    return created


@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: str,
    payload: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    document = await _load_document(db, document_id)
    if not _can_manage_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot edit this document.")

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Document title cannot be empty.")
        document.title = title
    if payload.category_id is not None:
        if payload.category_id:
            category = await db.get(DocumentCategory, payload.category_id)
            if not category:
                raise HTTPException(status_code=400, detail="The selected category does not exist.")
            document.category_id = category.id
        else:
            document.category_id = None
    if payload.academic_year is not None:
        document.academic_year = payload.academic_year.strip()

    await db.commit()
    return await _load_document(db, document_id)


@router.patch("/{document_id}/archive", response_model=DocumentOut)
async def archive_document(
    document_id: str,
    payload: DocumentArchiveInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    document = await _load_document(db, document_id)
    if not _can_manage_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot archive this document.")

    document.is_archived = payload.is_archived
    await db.commit()
    return await _load_document(db, document_id)


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    version_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    document = await _load_document(db, document_id)
    if not _can_access_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot download this document.")

    version = None
    if version_id:
        version = next((item for item in document.versions if item.id == version_id), None)
    else:
        version = document.versions[0] if document.versions else None
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found.")

    path = Path(version.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="The stored file could not be found.")
    return FileResponse(path, media_type=version.mime_type, filename=version.file_name)


@router.post("/{document_id}/versions", response_model=DocumentOut)
async def upload_document_version(
    document_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    document = await _load_document(db, document_id)
    if not _can_access_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot update this document.")

    filename = Path(file.filename or "document").name
    _validate_document_file(filename)
    file_bytes = await _read_limited_upload(file)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    checksum = compute_sha256(file_bytes)
    if any(version.sha256_checksum == checksum for version in document.versions):
        raise HTTPException(status_code=409, detail="This file is already one of the document versions.")

    extracted_text = extract_text(file_bytes, filename)
    next_version = max((version.version_number for version in document.versions), default=0) + 1
    os.makedirs("./uploads", exist_ok=True)
    local_path = f"./uploads/{checksum}_{filename}"
    with open(local_path, "wb") as target:
        target.write(file_bytes)

    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version,
        file_name=filename,
        file_path=local_path,
        file_size_bytes=len(file_bytes),
        mime_type=file.content_type or "application/octet-stream",
        sha256_checksum=checksum,
        extracted_text=extracted_text,
        uploaded_by=current_user.id,
    )
    db.add(version)
    document.current_version = next_version
    await db.commit()
    return await _load_document(db, document_id)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    document = await _load_document(db, document_id)
    if not _can_manage_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot delete this document.")

    paths = [Path(version.file_path) for version in document.versions]
    await db.delete(document)
    await db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    return Response(status_code=204)


@router.post("/import/google", response_model=DocumentOut)
async def import_google_document(
    payload: GoogleImportInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    download_url, fallback_filename, fallback_mime = _google_export_target(payload.url)
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            async with client.stream("GET", download_url) as response:
                if response.status_code in {401, 403}:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Google requires permission to open this file. Share it with "
                            "“Anyone with the link” or download it and upload it manually."
                        ),
                    )
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Google returned HTTP {response.status_code} for this file.",
                    )
                content_type = response.headers.get("content-type", fallback_mime)
                if "text/html" in content_type.lower():
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Google returned a sign-in page instead of the file. Make the "
                            "document viewable by anyone with the link, or upload a downloaded copy."
                        ),
                    )

                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File size exceeds limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                        )
                filename = _imported_filename(
                    content_type,
                    response.headers.get("content-disposition"),
                    fallback_filename,
                )
    except HTTPException:
        raise
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not reach Google Drive: {exc}",
        ) from exc

    _validate_document_file(filename)
    if not data:
        raise HTTPException(status_code=400, detail="Google returned an empty file.")

    upload = UploadFile(
        file=io.BytesIO(bytes(data)),
        filename=filename,
        headers=Headers({"content-type": content_type or fallback_mime}),
    )
    return await upload_document(
        file=upload,
        title=payload.title,
        category_id=payload.category_id,
        academic_year=payload.academic_year,
        db=db,
        current_user=current_user,
    )


@router.get("", response_model=List[DocumentOut])
async def list_documents(
    category_id: Optional[str] = None,
    academic_year: Optional[str] = None,
    include_archived: bool = Query(False),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Document)
        .options(*_document_options())
        .order_by(desc(Document.created_at))
        .offset(skip)
        .limit(limit)
    )
    if not include_archived:
        stmt = stmt.where(Document.is_archived.is_(False))
    if current_user.department_id:
        stmt = stmt.where(Document.department_id == current_user.department_id)
    if category_id:
        stmt = stmt.where(Document.category_id == category_id)
    if academic_year:
        stmt = stmt.where(Document.academic_year == academic_year)

    res = await db.execute(stmt)
    return [_attach_latest(document) for document in res.scalars().all()]


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
    q: str,
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Sub-second metadata and content-based keyword search.
    """
    start_time = time.perf_counter()

    pattern = f"%{q}%"
    stmt = (
        select(Document)
        .join(DocumentVersion, Document.id == DocumentVersion.document_id)
        .where(
            or_(
                Document.title.ilike(pattern),
                DocumentVersion.extracted_text.ilike(pattern),
                DocumentVersion.abstract_summary.ilike(pattern),
            ),
        )
        .options(selectinload(Document.category), selectinload(Document.versions))
        .distinct()
    )
    if not include_archived:
        stmt = stmt.where(Document.is_archived.is_(False))
    if current_user.department_id:
        stmt = stmt.where(Document.department_id == current_user.department_id)

    res = await db.execute(stmt)
    docs = res.scalars().all()
    for d in docs:
        if d.versions:
            d.latest_version = d.versions[0]

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    return {
        "total": len(docs),
        "items": docs,
        "query_latency_ms": round(latency_ms, 2)
    }


@router.get("/categories", response_model=List[CategoryOut])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(select(DocumentCategory).order_by(DocumentCategory.name))
    return result.scalars().all()


@router.post("/{document_id}/summarize", response_model=DocumentOut)
async def summarize_document(
    document_id: str,
    language: Literal["en", "km"] = Query("en"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.category), selectinload(Document.versions))
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.versions:
        raise HTTPException(status_code=400, detail="Document has no stored version.")
    version = document.versions[0]
    if not version.extracted_text:
        raise HTTPException(status_code=400, detail="No extracted text is available to summarize.")

    try:
        result = await llm_service.summarize_document(
            document.title, version.extracted_text, language=language
        )
    except AIServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    version.abstract_summary = result.get("abstract_summary")
    version.extracted_entities = (
        json.dumps(result.get("entities")) if result.get("entities") is not None else None
    )
    await db.commit()
    await db.refresh(version)
    document.latest_version = version
    return document


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document_detail(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.category), selectinload(Document.versions))
    )
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.versions:
        doc.latest_version = doc.versions[0]
    return doc
