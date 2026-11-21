import io
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any, List, Literal, Optional
from urllib.parse import unquote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.datastructures import Headers

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentFolder,
    DocumentPermission,
    DocumentVersion,
)
from app.models.user import User
from app.schemas.document import (
    CategoryOut,
    DocumentArchiveInput,
    DocumentFolderCreate,
    DocumentFolderOut,
    DocumentFolderUpdate,
    DocumentOut,
    DocumentSearchResponse,
    DocumentShareInput,
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


def _is_department_admin(user: User) -> bool:
    return user.is_superuser or any(
        role.role_name in {"System Admin", "Department Admin"} for role in user.roles
    )


def _document_permission(document: Document, user_id: str) -> str | None:
    for permission in document.permissions:
        if permission.user_id == user_id:
            return permission.permission
    return None


def _can_access_document(document: Document, user: User) -> bool:
    if user.is_superuser or document.owner_id == user.id:
        return True
    if not user.department_id:
        return True
    if document.is_restricted:
        return _document_permission(document, user.id) is not None or _is_department_admin(user)
    return document.department_id == user.department_id


def _can_edit_document(document: Document, user: User) -> bool:
    if user.is_superuser or document.owner_id == user.id or _is_department_admin(user):
        return True
    if not _can_access_document(document, user):
        return False
    return _document_permission(document, user.id) in {"edit", "manage"}


def _can_manage_document(document: Document, user: User) -> bool:
    if user.is_superuser or document.owner_id == user.id or _is_department_admin(user):
        return True
    return _document_permission(document, user.id) == "manage"


def _document_options():
    return (
        selectinload(Document.category),
        selectinload(Document.folder),
        selectinload(Document.versions),
        selectinload(Document.permissions).selectinload(DocumentPermission.user),
    )


def _attach_latest(document: Document) -> Document:
    document.latest_version = document.versions[0] if document.versions else None
    return document


async def _validate_folder(db: AsyncSession, folder_id: str | None, user: User) -> DocumentFolder | None:
    if not folder_id:
        return None
    folder = await db.get(DocumentFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=400, detail="The selected folder does not exist.")
    if user.department_id and folder.department_id != user.department_id:
        raise HTTPException(status_code=400, detail="The selected folder is outside your department.")
    return folder


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


async def _embedding_for_text(text: str) -> str | None:
    if not settings.GEMINI_API_KEY or not text.strip():
        return None
    try:
        values = await llm_service.embed_text(text)
    except AIServiceUnavailable:
        return None
    return json.dumps(values)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


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
    folder_id: Optional[str] = Form(None),
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
    embedding = await _embedding_for_text(extracted_text)

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

    folder = await _validate_folder(db, folder_id, current_user)

    # 8. Persist Document & Version in Database
    new_doc = Document(
        title=doc_title,
        category_id=category_id,
        department_id=dept_id,
        owner_id=current_user.id,
        academic_year=academic_year,
        folder_id=folder.id if folder else None,
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
        embedding=embedding,
        uploaded_by=current_user.id,
    )
    db.add(new_version)
    await db.commit()

    # Return refreshed document
    stmt = (
        select(Document)
        .where(Document.id == new_doc.id)
        .options(*_document_options())
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
    if "folder_id" in payload.model_fields_set:
        folder = await _validate_folder(db, payload.folder_id, current_user)
        document.folder_id = folder.id if folder else None
    if payload.is_restricted is not None:
        document.is_restricted = payload.is_restricted

    await db.commit()
    return await _load_document(db, document_id)


@router.post("/{document_id}/permissions", response_model=DocumentOut)
async def share_document(
    document_id: str,
    payload: DocumentShareInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    document = await _load_document(db, document_id)
    if not _can_manage_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot share this document.")
    if payload.permission not in {"view", "edit", "manage"}:
        raise HTTPException(status_code=400, detail="Permission must be view, edit or manage.")
    target = await db.get(User, payload.user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=400, detail="The selected user does not exist.")
    if target.department_id != document.department_id:
        raise HTTPException(status_code=400, detail="You can only share with your department.")
    existing = next(
        (item for item in document.permissions if item.user_id == target.id),
        None,
    )
    if existing:
        existing.permission = payload.permission
    else:
        db.add(
            DocumentPermission(
                document_id=document.id,
                user_id=target.id,
                permission=payload.permission,
                created_by=current_user.id,
            )
        )
    await db.commit()
    return await _load_document(db, document_id)


@router.delete("/{document_id}/permissions/{user_id}", status_code=204)
async def remove_document_permission(
    document_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    document = await _load_document(db, document_id)
    if not _can_manage_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot change sharing for this document.")
    permission = next((item for item in document.permissions if item.user_id == user_id), None)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found.")
    await db.delete(permission)
    await db.commit()
    return Response(status_code=204)


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
    if not _can_edit_document(document, current_user):
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
    embedding = await _embedding_for_text(extracted_text)
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
        embedding=embedding,
        uploaded_by=current_user.id,
    )
    db.add(version)
    document.current_version = next_version
    await db.commit()
    return await _load_document(db, document_id)


@router.post("/{document_id}/versions/{version_id}/restore", response_model=DocumentOut)
async def restore_document_version(
    document_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    document = await _load_document(db, document_id)
    if not _can_edit_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot restore this document.")
    version = next((item for item in document.versions if item.id == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found.")
    next_version = max((item.version_number for item in document.versions), default=0) + 1
    db.add(
        DocumentVersion(
            document_id=document.id,
            version_number=next_version,
            file_name=version.file_name,
            file_path=version.file_path,
            file_size_bytes=version.file_size_bytes,
            mime_type=version.mime_type,
            sha256_checksum=version.sha256_checksum,
            extracted_text=version.extracted_text,
            abstract_summary=version.abstract_summary,
            extracted_entities=version.extracted_entities,
            embedding=version.embedding,
            uploaded_by=current_user.id,
        )
    )
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
        folder_id=payload.folder_id,
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
    return [
        _attach_latest(document)
        for document in res.scalars().all()
        if _can_access_document(document, current_user)
    ]


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
    q: str,
    include_archived: bool = Query(False),
    semantic: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Full-text search, with optional embedding-based semantic ranking.
    """
    start_time = time.perf_counter()

    if semantic and settings.GEMINI_API_KEY:
        try:
            query_embedding = await llm_service.embed_text(q)
            stmt = select(Document).options(*_document_options())
            if not include_archived:
                stmt = stmt.where(Document.is_archived.is_(False))
            if current_user.department_id:
                stmt = stmt.where(Document.department_id == current_user.department_id)
            candidates = (await db.execute(stmt)).scalars().all()
            scored = []
            for document in candidates:
                if not _can_access_document(document, current_user):
                    continue
                scores = []
                for version in document.versions:
                    if not version.embedding:
                        continue
                    try:
                        version_embedding = json.loads(version.embedding)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    scores.append(_cosine_similarity(query_embedding, version_embedding))
                if scores and max(scores) >= 0.2:
                    scored.append((max(scores), document))

            if scored:
                scored.sort(key=lambda item: item[0], reverse=True)
                items = [_attach_latest(document) for _, document in scored[:50]]
                return {
                    "total": len(scored),
                    "items": items,
                    "query_latency_ms": round((time.perf_counter() - start_time) * 1000.0, 2),
                }
        except AIServiceUnavailable:
            pass

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
        .options(*_document_options())
        .distinct()
    )
    if not include_archived:
        stmt = stmt.where(Document.is_archived.is_(False))
    if current_user.department_id:
        stmt = stmt.where(Document.department_id == current_user.department_id)

    res = await db.execute(stmt)
    docs = [
        document
        for document in res.scalars().all()
        if _can_access_document(document, current_user)
    ]
    for d in docs:
        if d.versions:
            d.latest_version = d.versions[0]

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    return {
        "total": len(docs),
        "items": docs,
        "query_latency_ms": round(latency_ms, 2)
    }


@router.get("/share-users")
async def list_share_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(User).where(User.is_active.is_(True))
    if current_user.department_id:
        stmt = stmt.where(User.department_id == current_user.department_id)
    users = (await db.execute(stmt.order_by(User.full_name))).scalars().all()
    return [
        {"id": user.id, "full_name": user.full_name, "email": user.email}
        for user in users
        if user.id != current_user.id
    ]


@router.get("/folders", response_model=List[DocumentFolderOut])
async def list_folders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(DocumentFolder)
    if current_user.department_id:
        stmt = stmt.where(DocumentFolder.department_id == current_user.department_id)
    folders = (await db.execute(stmt.order_by(DocumentFolder.name))).scalars().all()
    count_stmt = select(Document.folder_id, func.count()).group_by(Document.folder_id)
    if current_user.department_id:
        count_stmt = count_stmt.where(Document.department_id == current_user.department_id)
    counts = {folder_id: count for folder_id, count in (await db.execute(count_stmt)).all()}
    return [
        DocumentFolderOut.model_validate(folder).model_copy(
            update={"document_count": counts.get(folder.id, 0)}
        )
        for folder in folders
    ]


@router.post("/folders", response_model=DocumentFolderOut)
async def create_folder(
    payload: DocumentFolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if not current_user.department_id:
        raise HTTPException(status_code=400, detail="Your account is not assigned to a department.")
    parent = await _validate_folder(db, payload.parent_id, current_user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name cannot be empty.")
    folder = DocumentFolder(
        name=name,
        parent_id=parent.id if parent else None,
        department_id=current_user.department_id,
        created_by=current_user.id,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@router.patch("/folders/{folder_id}", response_model=DocumentFolderOut)
async def update_folder(
    folder_id: str,
    payload: DocumentFolderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    folder = await db.get(DocumentFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if current_user.department_id and folder.department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="You cannot edit this folder.")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Folder name cannot be empty.")
        folder.name = name
    if "parent_id" in payload.model_fields_set:
        if payload.parent_id == folder.id:
            raise HTTPException(status_code=400, detail="A folder cannot contain itself.")
        parent = await _validate_folder(db, payload.parent_id, current_user)
        cursor = parent
        while cursor:
            if cursor.id == folder.id:
                raise HTTPException(status_code=400, detail="A folder cannot be moved inside its child.")
            cursor = await db.get(DocumentFolder, cursor.parent_id) if cursor.parent_id else None
        folder.parent_id = parent.id if parent else None
    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    folder = await db.get(DocumentFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if current_user.department_id and folder.department_id != current_user.department_id:
        raise HTTPException(status_code=403, detail="You cannot delete this folder.")
    await db.execute(
        update(Document).where(Document.folder_id == folder.id).values(folder_id=folder.parent_id)
    )
    await db.execute(
        update(DocumentFolder)
        .where(DocumentFolder.parent_id == folder.id)
        .values(parent_id=folder.parent_id)
    )
    await db.delete(folder)
    await db.commit()
    return Response(status_code=204)


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
    document = await _load_document(db, document_id)
    if not _can_access_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot access this document.")
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
    document = await _load_document(db, document_id)
    if not _can_access_document(document, current_user):
        raise HTTPException(status_code=403, detail="You cannot access this document.")
    return document
