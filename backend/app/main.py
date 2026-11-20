from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.security import get_password_hash
from app.models import Role, Department, User, DocumentCategory
from app.api.v1.router import api_router
from sqlalchemy import select


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize tables and seed master data if not present
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default data
    async with AsyncSessionLocal() as session:
        # 1. Seed Roles
        role_names = ["System Admin", "Department Admin", "Staff", "Student"]
        for r_name in role_names:
            stmt = select(Role).where(Role.role_name == r_name)
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                session.add(Role(role_name=r_name, description=f"{r_name} role"))

        # 2. Seed Default Department
        dept_stmt = select(Department).where(Department.department_code == "CS")
        dept_res = await session.execute(dept_stmt)
        cs_dept = dept_res.scalar_one_or_none()
        if not cs_dept:
            cs_dept = Department(
                department_code="CS",
                name="Computer Science and Engineering",
                faculty="Faculty of Science & Technology"
            )
            session.add(cs_dept)
            await session.flush()

        # 3. Seed Default Admin User
        admin_stmt = select(User).where(User.email == "admin@aub.edu.kh")
        admin_res = await session.execute(admin_stmt)
        if not admin_res.scalar_one_or_none():
            admin_role_stmt = select(Role).where(Role.role_name == "System Admin")
            admin_role = (await session.execute(admin_role_stmt)).scalar_one_or_none()

            admin_user = User(
                email="admin@aub.edu.kh",
                hashed_password=get_password_hash("Admin@AUB2026"),
                full_name="ACLEDA System Administrator",
                student_or_staff_id="AUB-ADMIN-01",
                department_id=cs_dept.id if cs_dept else None,
                is_active=True,
                is_superuser=True,
                roles=[admin_role] if admin_role else [],
            )
            session.add(admin_user)

        # 4. Seed Categories
        categories = [
            ("POLICY", "Academic Policy", "Institutional policies and circulars"),
            ("CURRICULUM", "Curriculum & Syllabus", "Course outlines and syllabi"),
            ("MOM", "Minutes of Meeting", "Official recorded minutes"),
            ("REPORT", "Department Report", "Semester and annual administrative reports"),
        ]
        for code, name, desc in categories:
            cat_stmt = select(DocumentCategory).where(DocumentCategory.code == code)
            cat_res = await session.execute(cat_stmt)
            if not cat_res.scalar_one_or_none():
                session.add(DocumentCategory(code=code, name=name, description=desc))

        await session.commit()

    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Automated Document and Meeting Management Ecosystem for ACLEDA University of Business.",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# Scalar API reference replaces the default Swagger UI.
@app.get("/docs", include_in_schema=False)
async def scalar_api_reference():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=f"{settings.APP_NAME} — API Reference",
        layout="modern",
        theme="default",
        telemetry=False,
        with_default_fonts=True,
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows development on web, localhost, and Chrome extensions
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "api_version": "v1",
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API Gateway",
        "docs_url": "/docs",
        "health_url": "/health",
    }
