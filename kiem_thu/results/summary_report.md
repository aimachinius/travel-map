# Báo Cáo Tổng Hợp Kết Quả Kiểm Thử Hiệu Năng (Round 1)

- **Thời gian thực hiện**: `2026-11-07`
- **Tổng số Test Case trong bộ kiểm thử**: `16` (Đã loại bỏ `TC_PERF_02`, `TC_PERF_03` theo yêu cầu)
- **Kết quả tổng quan Round 1**:
  - **Passed**: `5` (`TC_PERF_10`, `TC_PERF_11`, `TC_PERF_13`, `TC_PERF_14`, `TC_PERF_17`)
  - **Failed**: `10` (`TC_PERF_01`, `TC_PERF_04`, `TC_PERF_05`, `TC_PERF_06`, `TC_PERF_07`, `TC_PERF_08`, `TC_PERF_09`, `TC_PERF_12`, `TC_PERF_16`, `TC_PERF_18`)
  - **Pending (Người dùng tự kiểm thử thủ công trên trình duyệt)**: `1` (`TC_PERF_15`)

---

## 1. Thông Số Môi Trường Thực Thi Thực Tế

| Thành phần | Thông số đo thực tế | File Log / Bằng chứng |
|---|---|---|
| **Laptop Host** | Windows 11 Home, Intel Core i7-1195G7 (4C/8T @ 2.90GHz), RAM `7.894 MB` (Trống ban đầu `~750 - 1.000 MB`, chiếm dụng nền `~87 - 90%`) | [`env_audit.json`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/results/env_audit.json) |
| **PostgreSQL + PostGIS** | Container `foodspot-db` (`postgis/postgis:16-3.4-alpine`), `max_connections = 100`, `shared_buffers = 128MB`, GIST Index `idx_places_location` & `idx_discovery_scans_center_location` | [`env_audit.json`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/results/env_audit.json) |
| **Dữ liệu đã Seed** | `502` users ([`users_200.csv`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/data/users_200.csv)), `10.044` địa điểm tại Đà Nẵng, `600` videos, `2.604` `video_place_matches`, `1.028` `analysis_runs`, `2.201` `saved_places`, `2.201` `saved_videos` | [`seeded_ids.json`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/data/seeded_ids.json) |
| **Redis Queue & Cache** | Container `foodspot-redis` (`redis:7-alpine`), RAM sử dụng `~1.16 MB` (`7.6 MB` container RSS) | [`env_audit.json`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/results/env_audit.json) |
| **Google Colab AI Server** | Cloudflare Tunnel `https://flashers-characterized-history-drawings.trycloudflare.com/api/v1/extract` + SSH `8.tcp.us-cal-1.ngrok.io:20486` (`Tesla T4 15.360 MiB VRAM`, System RAM `12.975 MiB`) | [`ai_server_ssh_audit.log`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/logs/ai_server_ssh_audit.log), [`ssh_TC_PERF_10.log`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/logs/ssh_TC_PERF_10.log), [`ssh_TC_PERF_17.log`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/logs/ssh_TC_PERF_17.log) |

---

## 2. Bảng Tổng Hợp Kết Quả Từng Test Case (Round 1)

| Mã TC | Kịch bản kiểm thử | VUs / Tải mục tiêu | Kết quả đo thực tế (Steady-state) | SLA Kỳ vọng | Kết luận |
|---|---|---|---|---|---|
| **TC_PERF_01** | Đăng nhập & cấp JWT (`POST /api/v1/auth/login`) (2 Workers) | 30 VUs / 15 RPS (scale 1.0, 240s) | `3.113` reqs, `p50 = 419.36 ms`, `p95 = 2263.74 ms`, `Err = 0%`, CPU Avg `78.28%` (Peak `100%`) | `p95 < 500 ms`, `Err < 0.5%` | **Failed** |
| **TC_PERF_04** | Spike Test (`nearby` 90% + `login` 10%) (Backlog 512, 2 Workers) | 15 VUs (60s) $\rightarrow$ 120 VUs / 50 RPS (15s ramp + 60s hold) $\rightarrow$ 15 VUs (15s) | Baseline 15 VUs (60s): `635` reqs, `p50 = 55.19 ms`, `p95 = 361.18 ms`, `Err = 0%`; Spike 120 VUs: `1.018` reqs (`58` pass đầu pha), `p95 = 10026.86 ms`, `Err = 94.3%`. Worker Alive = `True` | Spike `p95 < 1500 ms`, `Err < 1%` | **Failed** |
| **TC_PERF_05** | Tìm kiếm địa điểm & Geocoding (80% Redis Cache + 20% ArcGIS) | 20 VUs / 5 RPS | `399` reqs, `p50 = 165.52 ms`, `p95 = 5013.24 ms`, `Err = 0%`, Cache Hit `80.2%`, Redis RAM `1.16 MB` | `p95 < 1200 ms`, `Err < 0.5%`, Redis `< 100 MB` | **Failed** |
| **TC_PERF_06** | Quét địa điểm bán kính 1–10 km (PostGIS GIST) | 80 VUs / 35 RPS | `604` reqs, `p95 = 10030.87 ms`, `Err = 94.86%` (Nghẽn `QueuePool(5, 10)`) | `p95 < 600 ms`, `Err < 0.1%` | **Failed** |
| **TC_PERF_07** | Sức bền quét bản đồ liên tục (Soak Test) | 40 VUs / 15 RPS | `2.537` reqs (`2.377` thành công), `p50 = 161.83 ms`, `p90 = 490.17 ms`, `p95 = 9995.72 ms`, `Err = 5.05%`, Không rò rỉ RAM/DB conn | `p95 < 500 ms`, `Err < 0.1%` | **Failed** |
| **TC_PERF_08** | Tiếp nhận URL video vào Analysis Queue | 50 VUs / 20 RPS | `922` reqs, `p50 = 48.7 ms`, `p95 = 9990.68 ms`, `Err = 5.20%` | `p95 < 400 ms`, `Err < 0.1%` | **Failed** |
| **TC_PERF_09** | Truy xuất video đã COMPLETED | 100 VUs / 45 RPS | `2.385` reqs, `p50 = 27.6 ms`, `p95 = 419.05 ms`, `Err = 4.48%`, `RPS = 40.57` | `p95 < 250 ms`, `Err = 0%` | **Failed** |
| **TC_PERF_10** | Xử lý AI Pipeline trên Google Colab Free (Tesla T4) | 6 videos thực tế (Concurrency 1–2) | `6/6` thành công (`Err = 0%`), `p50 = 19.34 s`, `p95 = 37.25 s`, VRAM Peak `3.77 GB / 15 GB`, Colab RAM Peak `5.34 GB / 12.7 GB` | `p95 < 45 s`, `Err < 5%`, VRAM `< 13.5 GB` | **Passed** |
| **TC_PERF_11** | Thông báo thời gian thực qua WebSocket | 150 kết nối WS đồng thời | `150/150` kết nối (`Dropped = 0`, `Err = 0%`), `4.700` bản tin, `p50 = 3.88 ms`, `p95 = 5.46 ms`, RAM tăng `39.88 MB` | `p95 < 150 ms`, `Err = 0%`, RAM `< 300 MB` | **Passed** |
| **TC_PERF_12** | Xem chi tiết quán & danh sách video liên quan | 80 VUs / 35 RPS | `3.389` reqs, `p50 = 14.99 ms`, `p95 = 387.62 ms`, nhưng nhánh `/places/{id}/videos` lỗi `500` (`Err = 54.18%`) | `p95 < 500 ms`, `Err < 0.1%` | **Failed** |
| **TC_PERF_13** | Lưu và bỏ lưu địa điểm/video yêu thích | 50 VUs / 20 RPS | `1.710/1.710` thành công (`Err = 0%`), `p50 = 17.39 ms`, `p95 = 292.44 ms`, `Deadlocks = 0` | `p95 < 350 ms`, `Err < 0.1%`, Zero Deadlock | **Passed** |
| **TC_PERF_14** | Truy xuất & phân trang danh sách đã lưu | 60 VUs / 25 RPS | `2.123/2.123` thành công (`Err = 0%`), `p50 = 21.06 ms`, `p95 = 402.47 ms`, Index Scan `0.54 ms` | `p95 < 600 ms`, `Err < 0.1%` | **Passed** |
| **TC_PERF_15** | Kết xuất bản đồ (Map Rendering) & phát video trên trình duyệt | 150 markers trên Chrome/Brave | *Để người dùng tự kiểm thử thủ công trên trình duyệt* | Tải `< 2.5s`, `>= 45 FPS`, RAM `< 400 MB` | **Pending** |
| **TC_PERF_16** | Tìm ngưỡng giới hạn (Breaking Point) trên Laptop 8GB | 50 $\rightarrow$ 100 $\rightarrow$ 150 $\rightarrow$ 200 $\rightarrow$ 250 VUs | Ngưỡng gãy tại `50 VUs` (`p95 = 10016.5 ms`, `Err = 51.4%`) do tràn `QueuePool(5, 10)` và treo event loop | Tự hồi phục `p95 < 500 ms` sau khi hạ tải | **Failed** |
| **TC_PERF_17** | Cơ chế xếp hàng (Backpressure) khi đẩy 30 video liên tiếp về Colab | 30 videos trong 30s | `30/30` trả `HTTP 202` (`p50 = 84.39 ms`, `p95 = 176.18 ms`, `Max = 178.52 ms`), Peak Queue `15` tasks, Worker xử lý tuần tự, VRAM `2.55 GB` | `HTTP 202 < 500 ms`, Xử lý tuần tự, Zero CUDA OOM | **Passed** |
| **TC_PERF_18** | Chịu lỗi khi Cloudflare Tunnel / Colab bị ngắt đột ngột | 30 VUs khi đứt Tunnel | Bản đồ `p50 = 55.92 ms`, `p95 = 744.58 ms` (`Err = 1.61%`); Task video chuyển sang `FAILED` thay vì `RETRY`, `AI_REQUEST_TIMEOUT = 180s` | Bản đồ `p95 < 600 ms` (`Err = 0%`), Task tự `RETRY/PENDING` | **Failed** |

---

## 3. Phân Tích Chuyên Sâu 5 Nút Cổ Chai & Lỗi Kiến Trúc Phát Hiện Qua Kiểm Thử

1. **Nút cổ chai số 1 — Deadlock giữa `async def` Endpoint và SQLAlchemy `QueuePool(pool_size=5, max_overflow=10)`** (Ảnh hưởng: `TC_PERF_04`, `TC_PERF_06`, `TC_PERF_07`, `TC_PERF_08`, `TC_PERF_16`, `TC_PERF_18`):
   - Trong [`backend/app/db/session.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/db/session.py#L6-L9), `create_engine(settings.database_url, pool_pre_ping=True)` sử dụng cấu hình mặc định của SQLAlchemy (`pool_size=5, max_overflow=10`, tối đa 15 kết nối).
   - Trong [`backend/app/api/v1/endpoints/places.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/api/v1/endpoints/places.py#L46) (`async def get_nearby_videos`) và [`videos.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/api/v1/endpoints/videos.py#L32) (`async def submit_video_endpoint`), hàm handler khai báo `async def` nhưng lại gọi trực tiếp các phương thức ORM đồng bộ (`db.execute`, `db.scalar`, `db.commit`) trên main `asyncio` event loop, đồng thời `BackgroundTasks` chạy `async def _trigger_discovery_task` cũng gọi `db.scalar` đồng bộ trên event loop.
   - Hệ quả: Khi số lượng VUs vượt quá 40–50, 15 kết nối DB bị giữ chặt trong khi chờ `anyio` worker thread đóng session (`finally: db.close()`), gây ra lỗi `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00`.
   - **Hướng khắc phục**: Tăng `pool_size=30, max_overflow=40` trong [`session.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/db/session.py) và bọc các lời gọi DB đồng bộ trong `async def` bằng `await asyncio.to_thread(...)` (hoặc chuyển sang `def` cho các bước DB đồng bộ).

2. **Nút cổ chai số 2 — Lỗi cú pháp SQLAlchemy `func.case(...)` trong `PlaceService.get_place_videos`** (Ảnh hưởng: `TC_PERF_12`):
   - Tại [`backend/app/services/place_service.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/services/place_service.py#L168), code viết `confidence_order = func.case(...)` khiến SQLAlchemy dịch thành hàm SQL `case(...)` không tồn tại trong PostgreSQL (gây lỗi `500 Internal Server Error` cho mọi request `GET /api/v1/places/{place_id}/videos`).
   - **Hướng khắc phục**: Đổi `from sqlalchemy import case` và gọi `case((VideoPlaceMatch.confidence_status == "HIGH", 1), ...)`.

3. **Nút cổ chai số 3 — Bão hòa CPU khi băm Argon2 trên 1 Uvicorn Worker** (Ảnh hưởng: `TC_PERF_01`):
   - [`backend/app/core/security.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/core/security.py#L9) sử dụng thuật toán `Argon2` (`pwdlib.PasswordHash.recommended()`) tiêu tốn CPU hơn Bcrypt, và [`backend/Dockerfile`](file:///d:/year_4/pbl/team_repo/travel-map/backend/Dockerfile#L27) chỉ chạy 1 tiến trình Uvicorn worker duy nhất, làm CPU chạm `100%` và đẩy `p95` lên `1.714 ms` ở tải 30 VUs / 15 RPS.

4. **Nút cổ chai số 4 — Quét tuần tự `unaccent` + `similarity` trên 10.044 địa điểm không có GIN Trigram Index** (Ảnh hưởng: `TC_PERF_05`):
   - Tại [`backend/app/services/place_service.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/services/place_service.py#L128-L138), truy vấn `GET /api/v1/places/search?q={keyword}` gọi `func.similarity(func.lower(func.unaccent(Place.name)), kw) >= 0.3` mà chưa có functional GIN index (`gin_trgm_ops`), cộng với 20% truy vấn gọi trực tiếp ra ArcGIS ngoài Internet khiến `p95` tăng lên `5.013 ms` dù `p50` chỉ `165.52 ms`.

5. **Nút cổ chai số 5 — Thiếu cơ chế `RETRY` và Timeout dài (`180s`) khi đứt kết nối Cloudflare Tunnel** (Ảnh hưởng: `TC_PERF_18`):
   - Tại [`backend/app/services/analysis_service.py`](file:///d:/year_4/pbl/team_repo/travel-map/backend/app/services/analysis_service.py#L379), khi kết nối tới AI Server thất bại, Worker gọi ngay `fail_analysis()` chuyển trạng thái sang `FAILED` thay vì đẩy lại hàng đợi với trạng thái `RETRY/PENDING`, và `AI_REQUEST_TIMEOUT` đang đặt `180s` thay vì `10s` cho bước kết nối.

