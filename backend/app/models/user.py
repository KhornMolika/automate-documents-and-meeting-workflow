import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

# Association table for Many-to-Many between Users and Roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime, default=datetime.utcnow),
)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    department_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty: Mapped[str] = mapped_column(String(255), default="Faculty of Science & Technology")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="department")
    documents = relationship("Document", back_populates="department")
    meetings = relationship("Meeting", back_populates="department")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_or_staff_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    department_id: Mapped[str] = mapped_column(String(36), ForeignKey("departments.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    department = relationship("Department", back_populates="users")
    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")
    uploaded_documents = relationship("Document", back_populates="owner")
    created_meetings = relationship("Meeting", back_populates="creator")
    meeting_participations = relationship("MeetingParticipant", back_populates="user")
    assigned_action_items = relationship("ActionItem", back_populates="responsible_person")
