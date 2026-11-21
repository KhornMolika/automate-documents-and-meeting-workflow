import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class DocumentCategory(Base):
    __tablename__ = "document_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    documents = relationship("Document", back_populates="category")


class DocumentFolder(Base):
    __tablename__ = "document_folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[str] = mapped_column(String(36), ForeignKey("document_folders.id"), nullable=True)
    department_id: Mapped[str] = mapped_column(String(36), ForeignKey("departments.id"), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parent = relationship("DocumentFolder", remote_side=[id], back_populates="children")
    children = relationship("DocumentFolder", back_populates="parent", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="folder")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("document_categories.id"), nullable=True)
    department_id: Mapped[str] = mapped_column(String(36), ForeignKey("departments.id"), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(50), default="2024-2025", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    folder_id: Mapped[str] = mapped_column(String(36), ForeignKey("document_folders.id"), nullable=True)
    drive_file_id: Mapped[str] = mapped_column(String(255), nullable=True)
    drive_web_link: Mapped[str] = mapped_column(String(500), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = relationship("DocumentCategory", back_populates="documents")
    department = relationship("Department", back_populates="documents")
    owner = relationship("User", back_populates="uploaded_documents")
    folder = relationship("DocumentFolder", back_populates="documents")
    permissions = relationship("DocumentPermission", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentVersion.version_number)")


class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    __table_args__ = (UniqueConstraint("document_id", "user_id", name="uq_document_permission"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(20), default="view")  # view, edit, manage
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="permissions")
    user = relationship("User", foreign_keys=[user_id])

    @property
    def full_name(self) -> str:
        return self.user.full_name if self.user else ""

    @property
    def email(self) -> str:
        return self.user.email if self.user else ""


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=True)
    abstract_summary: Mapped[str] = mapped_column(Text, nullable=True)
    extracted_entities: Mapped[str] = mapped_column(Text, nullable=True) # JSON-serialized entities
    embedding: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list of floats
    uploaded_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="versions")

    @property
    def contains_khmer(self) -> bool:
        return any(
            "\u1780" <= character <= "\u17ff"
            for character in (self.extracted_text or "")
        )
