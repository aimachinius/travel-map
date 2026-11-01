# Travel Map - Food Spot Monorepo

## 1. Project Overview & Focus Area
- **Core Active Development**: `backend/` (Food Spot FastAPI Backend + PostgreSQL + AI analysis pipeline).
- **Other Components**: `front/` (React/Vite Web App), `front_mobile/` (React Native / Expo App).
- Focus solely on `backend/` unless explicit instruction specifies frontend work.

## 2. System Specifications & Business Requirements
- Toàn bộ đặc tả hệ thống, cấu trúc database, các endpoint đã/chưa hoàn thành và roadmap phân tích video bằng AI được mô tả chi tiết tại: [`backend/README.md`](file:///d:/year_4/pbl/team_repo/travel-map/backend/README.md).
- Trước khi thực hiện thay đổi logic, thêm API hoặc chỉnh sửa model, hãy đối chiếu với [`backend/README.md`](file:///d:/year_4/pbl/team_repo/travel-map/backend/README.md).

## 3. Engineering Guidelines
- **Framework**: FastAPI (Async router handlers, Pydantic v2 schemas).
- **Service Layer Pattern**: Business logic đặt tại `backend/app/services/`, không viết trực tiếp trong router.
- **Database**: PostgreSQL thông qua SQLAlchemy ORM và Alembic migrations.
- **Testing**: Chạy và viết kiểm thử tại `backend/tests/` với `pytest`.
