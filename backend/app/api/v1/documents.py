import os
import time
import json
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy import select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentVersion, DocumentCategory
from app.schemas.document import DocumentOut, DocumentSearchResponse
from app.services.extractor import extract_text, compute_sha256
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/documents", tags=["Document Management"])


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
    dept_id = current_user.department_id or "default-dept"
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

    # 6. AI Summarization & Entity Extraction via Gemini
    ai_result = await gemini_service.summarize_document(doc_title, extracted_text)
    abstract_summary = ai_result.get("abstract_summary", "")
    entities_json = json.dumps(ai_result.get("entities", {}))

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


@router.get("", response_model=List[DocumentOut])
async def list_documents(
    category_id: Optional[str] = None,
    academic_year: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = (
        select(Document)
        .where(Document.is_archived == False)
        .options(selectinload(Document.category), selectinload(Document.versions))
        .order_by(desc(Document.created_at))
        .offset(skip)
        .limit(limit)
    )
    if category_id:
        stmt = stmt.where(Document.category_id == category_id)
    if academic_year:
        stmt = stmt.where(Document.academic_year == academic_year)

    res = await db.execute(stmt)
    docs = res.scalars().all()
    for d in docs:
        if d.versions:
            d.latest_version = d.versions[0]
    return docs


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
    q: str,
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
            )
        )
        .options(selectinload(Document.category), selectinload(Document.versions))
        .distinct()
    )

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
