---
paths:
  - "backend/**"
---

# Food Spot Backend Specifications & Architecture Rules

## 1. Domain Specification Reference
- **Source of Truth**: Chi tiết toàn bộ kiến trúc, database schema (7 bảng), danh sách API v1 và trạng thái phân tích video xem tại: [`backend/README.md`](file:///d:/year_4/pbl/team_repo/travel-map/backend/README.md).

## 2. Technical Stack & Conventions
- **Language**: Python 3.11+
- **Web Framework**: FastAPI (Async endpoints for I/O)
- **Database & ORM**: PostgreSQL, SQLAlchemy 2.0 (async sessions), Alembic migrations
- **Authentication**: JWT access tokens (passwords hashed using bcrypt/argon2, never leak in schemas)
- **Validation**: Pydantic v2 schemas (`backend/app/schemas/`)

## 3. Layer Separation Rules
1. **API Routers (`backend/app/api/`)**:
   - Chỉ chịu trách nhiệm parse request, validate authentication qua `Depends(deps.get_current_user)`, và trả response model.
   - Tuyệt đối không viết business logic hoặc gọi raw database queries tại router.
2. **Service Layer (`backend/app/services/`)**:
   - Toàn bộ business logic nằm ở đây (`auth_service.py`, `video_service.py`, `analysis_service.py`).
   - Nhận DB session qua tham số và thao tác với SQLAlchemy models.
3. **Database Models (`backend/app/models/`)**:
   - Định nghĩa quan hệ (`relationship`), foreign keys, constraints.
   - Khi thay đổi model, luôn tạo Alembic migration (`alembic revision --autogenerate -m "..."`).
4. **Testing (`backend/tests/`)**:
   - Viết test với `pytest` và `httpx.AsyncClient`.
