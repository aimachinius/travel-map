# Food Spot Backend

Backend của dự án Food Spot, xây dựng bằng FastAPI và PostgreSQL. Backend chịu trách nhiệm quản lý tài khoản, dữ liệu video, yêu cầu phân tích và kết nối với các chức năng xử lý AI của hệ thống.

## 1. Công nghệ sử dụng

- **Python**: Ngôn ngữ lập trình.
- **FastAPI**: Xây dựng REST API.
- **PostgreSQL**: Hệ quản trị cơ sở dữ liệu.
- **SQLAlchemy**: ORM thao tác với database.
- **Alembic**: Quản lý database migration.
- **Pydantic**: Kiểm tra và xác thực dữ liệu request/response.
- **JWT**: Xác thực người dùng.
- **Uvicorn**: Chạy FastAPI server.
- **Pytest**: Kiểm thử.

## 2. Cấu trúc thư mục

```text
backend/
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py
│   │       │   ├── health.py
│   │       │   └── videos.py
│   │       └── router.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   │
│   ├── db/
│   │   └── session.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── place.py
│   │   ├── video.py
│   │   ├── video_place_match.py
│   │   ├── analysis_run.py
│   │   ├── saved_video.py
│   │   └── saved_place.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   └── video.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── video_service.py
│   │   └── analysis_service.py
│   │
│   └── main.py
│
├── alembic/
├── tests/
├── .env.example
├── alembic.ini
├── requirements.txt
└── README.md
```

### Vai trò các thư mục

| Thư mục | Chức năng |
|---|---|
| `api/` | Khai báo và tổ chức các API endpoint |
| `api/v1/endpoints/` | Các API theo từng nhóm chức năng |
| `core/` | Cấu hình ứng dụng và bảo mật |
| `db/` | Kết nối và quản lý database session |
| `models/` | Các model tương ứng với bảng PostgreSQL |
| `schemas/` | Định nghĩa dữ liệu đầu vào và đầu ra |
| `services/` | Xử lý logic nghiệp vụ |
| `alembic/` | Quản lý lịch sử thay đổi database |
| `tests/` | Nơi viết các bài kiểm thử |

## 3. Database

Sử dụng PostgreSQL.

Database hiện có 7 bảng:

| Bảng | Chức năng |
|---|---|
| `users` | Thông tin tài khoản người dùng |
| `places` | Thông tin địa điểm |
| `videos` | Thông tin video từ các nền tảng |
| `video_place_matches` | Liên kết video với địa điểm |
| `analysis_runs` | Lưu các yêu cầu và trạng thái phân tích video |
| `saved_videos` | Lưu video yêu thích của người dùng |
| `saved_places` | Lưu địa điểm yêu thích của người dùng |

Database được quản lý bằng SQLAlchemy và Alembic.

## 4. Các chức năng đã triển khai

### 4.1. Authentication

| Method | Endpoint | Chức năng |
|---|---|---|
| POST | `/api/v1/auth/register` | Đăng ký tài khoản |
| POST | `/api/v1/auth/login` | Đăng nhập |
| GET | `/api/v1/auth/me` | Lấy thông tin tài khoản hiện tại |

- Mật khẩu được hash trước khi lưu vào database.
- Đăng nhập hỗ trợ username hoặc email.
- Sử dụng JWT để xác thực các API cần đăng nhập.
- Kiểm tra tài khoản còn hoạt động trước khi cho phép truy cập.

### 4.2. Video

| Method | Endpoint | Chức năng |
|---|---|---|
| POST | `/api/v1/videos/submit` | Gửi URL video để tạo yêu cầu phân tích |
| GET | `/api/v1/videos` | Lấy danh sách video người dùng đã gửi |
| GET | `/api/v1/videos/{video_id}` | Xem chi tiết video |
| GET | `/api/v1/videos/analysis` | Lấy lịch sử phân tích |
| GET | `/api/v1/videos/analysis/{analysis_run_id}` | Xem trạng thái một yêu cầu phân tích |

Hiện tại:
- Hỗ trợ nhận diện URL YouTube và TikTok theo các mẫu URL đã triển khai.
- Trích xuất nền tảng và ID video.
- Kiểm tra video đã tồn tại để tránh tạo bản ghi video trùng lặp.
- Mỗi lần gửi URL sẽ tạo một `analysis_run` mới.
- Danh sách video chỉ hiển thị những video có yêu cầu phân tích thuộc tài khoản hiện tại.
- Kiểm tra quyền truy cập khi xem chi tiết video và yêu cầu phân tích.

### 4.3. Analysis Service

Đã xây dựng các hàm xử lý trạng thái phân tích:

| Trạng thái | Ý nghĩa |
|---|---|
| `PENDING` | Đang chờ xử lý |
| `PROCESSING` | Đang phân tích |
| `COMPLETED` | Phân tích hoàn tất |
| `FAILED` | Phân tích thất bại |

Các hàm service:
- `start_analysis()`: Bắt đầu phân tích.
- `complete_analysis()`: Hoàn thành phân tích.
- `fail_analysis()`: Đánh dấu yêu cầu thất bại.

Lưu ý: Các hàm trên hiện đã được kiểm thử trực tiếp ở service, chưa kết nối với worker hoặc pipeline AI thực tế.

## 5. Các chức năng đã kiểm thử

Các kiểm thử dưới đây đã được thực hiện trong môi trường phát triển local.

| Chức năng | Cách kiểm thử | Kết quả |
|---|---|---|
| Kết nối PostgreSQL | Chạy kiểm tra kết nối database | Thành công |
| Database migration | `alembic upgrade head` | Thành công |
| Đăng ký | Gọi API register | Thành công |
| Đăng nhập | Gọi API login | Thành công |
| JWT authentication | Gọi API `/auth/me` bằng token | Thành công |
| Gửi URL video | Gọi API submit | Thành công |
| Nhận diện YouTube URL | Kiểm tra platform và video ID | Thành công với URL mẫu |
| Danh sách video | Gọi API GET videos | Thành công |
| Chi tiết video | Gọi API GET video detail | Thành công |
| Lịch sử phân tích | Gọi API GET analysis | Thành công |
| Phân quyền video | Đăng nhập tài khoản thứ hai và thử truy cập video của tài khoản thứ nhất | Trả về 404 đúng mong đợi |
| Chuyển trạng thái phân tích | Gọi trực tiếp các hàm service | Thành công |

Lưu ý: Đây là kết quả kiểm thử trong môi trường local, không phải kết quả kiểm thử production. Chưa có bộ integration test tự động bao phủ toàn bộ API.

## 6. Các chức năng chưa triển khai hoàn chỉnh

Các thành phần sau vẫn đang trong quá trình phát triển hoặc chờ tích hợp với các module khác trong nhóm:

### Video và AI
- Tải video thực tế từ TikTok/YouTube.
- Lấy metadata thực tế như tiêu đề, thumbnail, tác giả và lượt xem.
- Kết nối module scraping.
- Tích hợp pipeline STT, OCR và phân tích hình ảnh.
- Kết hợp kết quả AI để nhận diện địa điểm.
- Lưu kết quả phân tích thực tế vào database.
- Tự động cập nhật trạng thái khi pipeline xử lý xong.

### Place và Search
- API tìm kiếm địa điểm.
- API xem chi tiết địa điểm.
- Tìm kiếm theo tọa độ và bán kính.
- API lấy danh sách video liên quan đến địa điểm.
- Sắp xếp video theo độ liên quan và dữ liệu tương tác.

### Saved
- API lưu và bỏ lưu video.
- API lấy danh sách video đã lưu.
- API lưu và bỏ lưu địa điểm.
- API lấy danh sách địa điểm đã lưu.

### Kiểm thử và triển khai
- Hoàn thiện unit test và integration test.
- Kiểm thử kết nối frontend web/mobile.
- Kiểm thử toàn bộ luồng xử lý video và AI.
- Chuẩn bị cấu hình triển khai trên server.

## 7. Yêu cầu môi trường

Cần cài đặt:

- Python 3.11 trở lên (khuyến nghị sử dụng phiên bản tương thích với các dependencies trong `requirements.txt`).
- PostgreSQL.
- Git.
- Visual Studio Code hoặc IDE tương đương.

## 8. Hướng dẫn cài đặt và chạy backend

### Bước 1. Clone repository

Clone repository của nhóm, sau đó mở terminal tại thư mục `backend`.

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY_FOLDER>/backend
```

### Bước 2. Tạo môi trường ảo

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Nếu PowerShell không cho phép kích hoạt môi trường ảo, có thể chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

### Bước 3. Cài đặt thư viện

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 4. Tạo database PostgreSQL

Mở PostgreSQL hoặc pgAdmin và tạo database:

```sql
CREATE DATABASE foodspot_db;
```

Mỗi thành viên có thể sử dụng database local riêng, không cần chia sẻ mật khẩu PostgreSQL.

### Bước 5. Cấu hình môi trường

Sao chép `.env.example` thành `.env`:

```powershell
Copy-Item .env.example .env
```

Cập nhật các thông tin kết nối database và JWT trong file `.env` theo máy cá nhân.

Không sử dụng chung mật khẩu database hoặc JWT secret giữa các môi trường.

### Bước 6. Chạy database migration

```powershell
alembic upgrade head
```

Lệnh này tạo các bảng database theo các migration đã có trong repository.

Không cần tự tạo 7 bảng bằng tay.

### Bước 7. Khởi chạy backend

```powershell
uvicorn app.main:app --reload
```

Backend mặc định chạy tại:

```text
http://127.0.0.1:8000
```

## 9. API Documentation

Sau khi server chạy thành công:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json

Có thể sử dụng Swagger UI hoặc Postman để kiểm tra các API.

Các API yêu cầu đăng nhập cần gửi JWT trong header:

```text
Authorization: Bearer <ACCESS_TOKEN>
```

## 10. Lưu ý khi phát triển chung

- Không commit file `.env`.
- Không commit thư mục `.venv/`.
- Không commit `__pycache__/` hoặc file cache.
- Khi thêm hoặc thay đổi model database, cần tạo migration bằng Alembic.
- Không tự ý sửa cấu trúc database mà không thông báo các thành viên liên quan.
- API endpoint nên tập trung nhận request, kiểm tra quyền và trả response.
- Logic nghiệp vụ nên được đặt trong `services/`.
- Dữ liệu request/response nên được định nghĩa trong `schemas/`.
- Khi tích hợp AI, cần thống nhất định dạng dữ liệu đầu vào và đầu ra giữa backend và nhóm AI.

---

**Trạng thái hiện tại:** Backend đã có nền tảng FastAPI, PostgreSQL, xác thực người dùng và các API quản lý video cơ bản. Các chức năng phân tích video bằng AI và khám phá địa điểm vẫn cần tiếp tục triển khai và tích hợp.