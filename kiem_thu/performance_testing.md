# Kiểm thử hiệu năng hệ thống

- **Feature:** Hệ thống Bản đồ Khám phá Địa điểm Ẩm thực & Phân tích Video Review bằng AI
- **Test requirement:** Đánh giá toàn diện hiệu năng hệ thống (Load Test, Endurance/Soak Test, Spike Test, Stress Test & Client Rendering) trên các luồng: Xác thực người dùng, Tìm kiếm & Quét bán kính địa điểm (PostGIS/Nominatim), Tiếp nhận & Phân tích Video qua AI Pipeline, Thông báo thời gian thực (WebSocket), và Quản lý địa điểm cá nhân.
- **Số lượng Test Case khai báo:** 16

## Thống kê theo vòng kiểm thử

| Vòng kiểm thử | Passed | Failed | Pending | N/A |
|---|---:|---:|---:|---:|
| Round 1 | 5 | 11 | 0 | 0 |
| Round 2 | 15 | 0 | 1 | 0 |
| Round 3 | 0 | 0 | 0 | 0 |

## Danh sách Test Cases

### NHÓM 0: Nhóm chức năng Xác thực Người dùng, Cấp phát Token và Khởi tạo Phiên

#### TC_PERF_01 — Kiểm thử tải đăng nhập và cấp phát JWT Token

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải đăng nhập và cấp phát JWT Token

**Quy trình & tham số thực thi:**

1. Endpoint: POST /api/v1/auth/login  
2. Dữ liệu: File users_200.csv (email, password hợp lệ).  
3. Kịch bản tải: Ramp-up 0 -> 30 VUs trong 30 giây; Duy trì 30 VUs, 15 req/giây trong 3 phút; Ramp-down 30 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 500 ms, Error Rate < 0,5%.  
• Laptop SLA: CPU < 85% (do Bcrypt hash tốn CPU), Tổng RAM hệ thống < 90% (còn trống >= 700 MB RAM vật lý).

**Điều kiện tiên quyết:**

FastAPI chạy 2 Uvicorn workers; Seed sẵn 500 user.

**Round 1:**

**Failed**
- **Client Metrics (Steady-state)**: Tổng `3113` reqs (Steady `2621` reqs, `14.48 req/s`) | p50 = `419.36 ms`, p95 = `2263.74 ms`, p99 = `4124.97 ms`, Avg = `644.26 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `78.28%` (Peak `100.0%`), RAM Avg = `87.52%` (Min Free `292.0 MB`, RAM Delta `-91.18 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `password_hash_algorithm=Argon2 (pwdlib.PasswordHash.recommended)`, `users_csv_count=200`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `4427` reqs (Steady `3036` reqs, `16.85 req/s`) | p50 = `51.58 ms`, p95 = `68.46 ms`, p99 = `217.71 ms`, Avg = `57.37 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `16.21%` (Peak `89.6%`), RAM Avg = `87.97%` (Min Free `315.55 MB`, RAM Delta `90.35 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `password_hash_algorithm=Argon2 (pwdlib.PasswordHash.recommended)`, `users_csv_count=200`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Giảm VUs (30 VUs, 15 RPS) phù hợp CPU 4 nhân/8 luồng khi băm Bcrypt

---

#### TC_PERF_04 — Kiểm thử tăng tải đột biến (Spike) khi người dùng truy cập đồng loạt

**Loại kiểm thử:**

Spike Test

**Mô tả kịch bản:**

Kiểm thử tăng tải đột biến (Spike) khi người dùng truy cập đồng loạt

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/places/nearby (90%) + POST /api/v1/auth/login (10%)  
2. Kịch bản tải: Nền 15 VUs trong 1 phút -> Tăng vọt (Spike) lên 120 VUs (50 req/giây) trong 15 giây -> Duy trì 1 phút -> Hạ về 15 VUs trong 15 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: Trong pha Spike p95 < 1.500 ms, Error Rate < 1%; Phục hồi p95 < 500 ms sau khi hạ tải 20 giây.  
• Laptop SLA: Không bị treo máy (Pagefile thrashing), Uvicorn worker không bị kill.

**Điều kiện tiên quyết:**

Uvicorn cấu hình --backlog 512; PostgreSQL max_connections = 100.

**Round 1:**

**Failed**
- **Baseline (15 VUs trong 60.54s)**: Tổng `635` reqs | p50 = `55.19 ms`, p95 = `361.18 ms`, Error Rate = `0.0%`
- **Spike Ramp-up (120 VUs / 50 RPS trong 23.87s)**: Tổng `298` reqs | p50 = `10013.13 ms`, p95 = `10021.14 ms`, Error Rate = `80.537%`
- **Spike Hold (120 VUs / 50 RPS trong 62.49s)**: Tổng `720` reqs | p50 = `10016.54 ms`, p95 = `10027.61 ms`, Error Rate = `100.0%` (Tổng hợp Spike: `1018` reqs, p95 = `10026.86 ms`, Err = `94.303%`)
- **Recovery (15 VUs trong 20.72s)**: Tổng `30` reqs | p50 = `10015.62 ms`, p95 = `10030.79 ms`, Error Rate = `100.0%` | Worker Alive = `True`
- **Laptop & Hạ tầng**: CPU Avg = `27.09%` (Peak `78.3%`), RAM Avg = `90.12%` (Min Free `629.49 MB`, RAM Delta `-4.44 MB`) | Tỷ lệ request thực tế: `nearby=1516 (90.1%), login=167 (9.9%)`
- **Xác minh điều kiện tiên quyết**: `Uvicorn --backlog=512` (Workers: `2`), `PostgreSQL max_connections=100` -> **ĐẠT**

**Round 2:**

**Passed**
- **Baseline (15 VUs trong 60.05s)**: Tổng `1119` reqs | p50 = `8.84 ms`, p95 = `58.59 ms`, Error Rate = `0.0%`
- **Spike Ramp-up (120 VUs / 50 RPS trong 15.34s)**: Tổng `1531` reqs | p50 = `27.26 ms`, p95 = `508.64 ms`, Error Rate = `0.0%`
- **Spike Hold (120 VUs / 50 RPS trong 60.34s)**: Tổng `3698` reqs | p50 = `9.42 ms`, p95 = `320.72 ms`, Error Rate = `0.0%` (Tổng hợp Spike: `5229` reqs, p95 = `392.74 ms`, Err = `0.0%`)
- **Recovery (15 VUs trong 15.05s)**: Tổng `697` reqs | p50 = `14.02 ms`, p95 = `98.01 ms`, Error Rate = `0.0%` | Worker Alive = `True`
- **Laptop & Hạ tầng**: CPU Avg = `16.64%` (Peak `48.0%`), RAM Avg = `89.09%` (Min Free `578.88 MB`, RAM Delta `-26.17 MB`) | Tỷ lệ request thực tế: `nearby=6342 (90.0%), login=703 (10.0%)`
- **Xác minh điều kiện tiên quyết**: `Uvicorn --backlog=512` (Workers: `2`), `PostgreSQL max_connections=100` -> **ĐẠT**

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Spike từ 15 -> 120 VUs sát ngưỡng chịu đựng thực tế của máy 8GB RAM

---

### NHÓM 1: Nhóm chức năng Tìm kiếm và Khám phá địa điểm trên bản đồ

#### TC_PERF_05 — Kiểm thử tải tìm kiếm địa điểm qua Geocoding (Có Redis Cache / Mock)

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải tìm kiếm địa điểm qua Geocoding (Có Redis Cache / Mock)

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/places/geocode?q={keyword}  
2. Kịch bản tải: Ramp-up 0 -> 20 VUs trong 30 giây; Duy trì 20 VUs, 5 req/giây trong 3 phút (80% từ khóa phổ biến vào Redis Cache, 20% gọi Mock/ArcGIS/Nominatim).

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 1.200 ms, Error Rate < 0,5%.  
• Laptop SLA: Không cần chạy container Nominatim nặng (tốn 8GB RAM); dùng Mock/Redis Cache giữ RAM < 100 MB.

**Điều kiện tiên quyết:**

Bật Redis Geocode Cache hoặc Mock Geocoding Server (do laptop 8GB RAM không thể tự host toàn bộ DB Nominatim).

**Round 1:**

**Failed**
- **Client Metrics (Steady-state)**: Tổng `422` reqs (Steady `295` reqs, `6.43 req/s`) | p50 = `154.92 ms`, p95 = `4475.18 ms`, p99 = `8767.67 ms`, Avg = `736.91 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `41.34%` (Peak `100.0%`), RAM Avg = `91.47%` (Min Free `528.09 MB`, RAM Delta `-134.8 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `route_mapping_note=Tài liệu ghi GET /api/v1/places/geocode?q={keyword}; Thực tế Backend triển khai GET /api/v1/places/search?q={keyword} và ArcGISGeocoder.`, `redis_used_memory_human=1.14M`, `redis_used_memory_mb=1.14`, `cache_hits=338`, `cache_misses_external_calls=84`, `cache_hit_ratio_pct=80.09`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `1015` reqs (Steady `695` reqs, `18.97 req/s`) | p50 = `7.15 ms`, p95 = `717.69 ms`, p99 = `748.67 ms`, Avg = `146.19 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `14.11%` (Peak `33.8%`), RAM Avg = `88.51%` (Min Free `715.68 MB`, RAM Delta `-52.77 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `route_mapping_note=Tài liệu ghi GET /api/v1/places/geocode?q={keyword}; Thực tế Backend triển khai GET /api/v1/places/search?q={keyword} và ArcGISGeocoder.`, `redis_used_memory_human=1.27M`, `redis_used_memory_mb=1.27`, `cache_hits=812`, `cache_misses_external_calls=203`, `cache_hit_ratio_pct=80.0`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Giảm từ 100 VUs/20 RPS xuống 20 VUs/5 RPS và dùng Cache/Mock để không tràn RAM

---

#### TC_PERF_06 — Kiểm thử tải quét địa điểm bán kính 1-10 km (PostGIS Spatial Query)

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải quét địa điểm bán kính 1-10 km (PostGIS Spatial Query)

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/places/within-radius?lat={lat}&lng={lng}&radius_km={r}  
2. Kịch bản tải: Ramp-up 0 -> 80 VUs trong 30 giây; Duy trì 80 VUs, 35 req/giây trong 5 phút; Ramp-down 30 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 600 ms, Error Rate < 0,1%.  
• Laptop SLA: PostgreSQL shared_buffers giới hạn 512MB, truy vấn dùng GIST Index < 50 ms.

**Điều kiện tiên quyết:**

PostgreSQL + PostGIS có sẵn 10.000 địa điểm tại Đà Nẵng; Đã tạo chỉ mục không gian GIST.

**Round 1:**

**Failed**
- **Client Metrics (Steady-state)**: Tổng `692` reqs (Steady `536` reqs, `8.37 req/s`) | p50 = `10014.82 ms`, p95 = `10029.71 ms`, p99 = `10039.6 ms`, Avg = `9055.72 ms`, Error Rate = `89.552%`
- **Laptop & Hạ tầng**: CPU Avg = `35.7%` (Peak `87.1%`), RAM Avg = `91.56%` (Min Free `539.16 MB`, RAM Delta `-98.27 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `execution_time_ms=71.988`, `planning_time_ms=16.151`, `uses_index_in_plan=True`, `shared_buffers=128MB`, `active_db_connections=1`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `4693` reqs (Steady `2814` reqs, `46.69 req/s`) | p50 = `8.82 ms`, p95 = `257.88 ms`, p99 = `569.19 ms`, Avg = `45.01 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `18.48%` (Peak `61.2%`), RAM Avg = `88.39%` (Min Free `718.7 MB`, RAM Delta `157.01 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `execution_time_ms=79.274`, `planning_time_ms=52.778`, `uses_index_in_plan=True`, `shared_buffers=128MB`, `active_db_connections=15`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Hiệu chỉnh từ 500 VUs/150 RPS xuống 80 VUs/35 RPS trong 5 phút

---

#### TC_PERF_07 — Kiểm thử sức bền quét bản đồ liên tục

**Loại kiểm thử:**

Endurance / Soak Test

**Mô tả kịch bản:**

Kiểm thử sức bền quét bản đồ liên tục

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/places/within-radius  
2. Kịch bản tải: Ramp-up 0 -> 40 VUs trong 1 phút; Duy trì 40 VUs, 15 req/giây liên tục trong 15 phút; Ramp-down 1 phút.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 500 ms ổn định suốt 15 phút, Error Rate < 0,1%.  
• Laptop SLA: Không rò rỉ RAM (Memory Leak < 50 MB sau 15 phút), không rò rỉ kết nối DB, CPU không bị hạ xung (thermal throttling).

**Điều kiện tiên quyết:**

Tâm bản đồ mặc định tại Đà Nẵng bán kính 5 km; Cắm sạc laptop và bật chế độ High Performance.

**Round 1:**

**Failed**
- **Client Metrics (Steady-state)**: Tổng `1111` reqs (Steady `950` reqs, `5.18 req/s`) | p50 = `10010.18 ms`, p95 = `10026.69 ms`, p99 = `10029.86 ms`, Avg = `6909.46 ms`, Error Rate = `67.368%`
- **Laptop & Hạ tầng**: CPU Avg = `29.86%` (Peak `70.7%`), RAM Avg = `91.18%` (Min Free `485.55 MB`, RAM Delta `-16.39 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `db_connections_before=1`, `db_connections_after=1`, `db_connection_leak_detected=False`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `4898` reqs (Steady `3536` reqs, `19.63 req/s`) | p50 = `7.83 ms`, p95 = `108.19 ms`, p99 = `280.45 ms`, Avg = `23.27 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `14.63%` (Peak `47.8%`), RAM Avg = `88.76%` (Min Free `737.41 MB`, RAM Delta `-250.87 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `db_connections_before=15`, `db_connections_after=15`, `db_connection_leak_detected=False`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Rút ngắn từ 2 giờ xuống 15 phút với 40 VUs để tránh ngắt kết nối Colab & quá nhiệt laptop

---

### NHÓM 2: Nhóm chức năng Phân tích Video Review (Colab Free T4) và Thông báo WebSocket

#### TC_PERF_08 — Kiểm thử tải tiếp nhận URL video vào hàng đợi xử lý (Analysis Queue)

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải tiếp nhận URL video vào hàng đợi xử lý (Analysis Queue)

**Quy trình & tham số thực thi:**

1. Endpoint: POST /api/v1/videos/analyze  
2. Kịch bản tải: Ramp-up 0 -> 50 VUs trong 30 giây; Duy trì 50 VUs, 20 req/giây trong 3 phút; Ramp-down 30 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: Phản hồi HTTP 202 Accepted với p95 < 400 ms, Error Rate < 0,1%.  
• Laptop SLA: 100% tác vụ đẩy vào Redis Queue thành công mà không gọi trực tiếp sang Colab ở bước tiếp nhận.

**Điều kiện tiên quyết:**

Người dùng đã đăng nhập; Analysis Queue (Redis) hoạt động ổn định trên máy local.

**Round 1:**

**Failed**
- **Client Metrics (Steady-state)**: Tổng `1154` reqs (Steady `962` reqs, `17.49 req/s`) | p50 = `73.44 ms`, p95 = `9990.68 ms`, p99 = `10016.91 ms`, Avg = `608.58 ms`, Error Rate = `5.198%`
- **Laptop & Hạ tầng**: CPU Avg = `25.55%` (Peak `71.3%`), RAM Avg = `90.59%` (Min Free `649.02 MB`, RAM Delta `-20.58 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `redis_queue_high_priority_len_before_cleanup=1045`, `total_enqueued_in_db=1087`, `cleaned_up_synthetic_tasks=True`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `2033` reqs (Steady `1210` reqs, `26.72 req/s`) | p50 = `62.08 ms`, p95 = `310.81 ms`, p99 = `378.74 ms`, Avg = `103.36 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `32.82%` (Peak `85.2%`), RAM Avg = `89.84%` (Min Free `712.8 MB`, RAM Delta `164.29 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `redis_queue_high_priority_len_before_cleanup=1938`, `total_enqueued_in_db=2033`, `cleaned_up_synthetic_tasks=True`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Hiệu chỉnh 50 VUs / 20 RPS phù hợp tốc độ đẩy Queue trên laptop

---

#### TC_PERF_09 — Kiểm thử tải truy xuất video đã có kết quả phân tích (Completed Videos)

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải truy xuất video đã có kết quả phân tích (Completed Videos)

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/videos/{video_id}/result  
2. Kịch bản tải: Ramp-up 0 -> 100 VUs trong 30 giây; Duy trì 100 VUs, 45 req/giây trong 3 phút; Ramp-down 30 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 250 ms, Error Rate = 0%.  
• Laptop SLA: Truy xuất từ DB/Redis Cache mượt mà, CPU < 70%.

**Điều kiện tiên quyết:**

Tối thiểu 500 URL video đã có trạng thái COMPLETED trong Database.

**Round 1:**

**Failed**
- **Client Metrics (Steady-state)**: Tổng `2783` reqs (Steady `2232` reqs, `40.57 req/s`) | p50 = `26.99 ms`, p95 = `419.05 ms`, p99 = `10023.6 ms`, Avg = `489.71 ms`, Error Rate = `4.48%`
- **Laptop & Hạ tầng**: CPU Avg = `19.56%` (Peak `46.2%`), RAM Avg = `89.83%` (Min Free `723.89 MB`, RAM Delta `-13.36 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `completed_analysis_runs_pool=408`, `completed_videos_pool=408`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `5148` reqs (Steady `2924` reqs, `64.63 req/s`) | p50 = `6.42 ms`, p95 = `229.47 ms`, p99 = `541.52 ms`, Avg = `43.02 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `23.16%` (Peak `55.3%`), RAM Avg = `91.14%` (Min Free `557.59 MB`, RAM Delta `8.17 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `completed_analysis_runs_pool=408`, `completed_videos_pool=408`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Hiệu chỉnh từ 500 VUs/120 RPS xuống 100 VUs/45 RPS

---

#### TC_PERF_10 — Kiểm thử tải xử lý AI Pipeline trên Google Colab Free (Tesla T4 GPU)

**Loại kiểm thử:**

Load Test (AI Colab)

**Mô tả kịch bản:**

Kiểm thử tải xử lý AI Pipeline trên Google Colab Free (Tesla T4 GPU)

**Quy trình & tham số thực thi:**

1. Luồng xử lý: Laptop gửi task qua Cloudflare Tunnel -> Colab Free (Tesla T4 15GB VRAM) chạy Keyframe v2 + DBNet + Vintern-1B + PhoWhisper -> Trả kết quả.  
2. Kịch bản tải: 5 VUs gửi tuần tự/song song giới hạn (Worker concurrency = 1 đến 2 trên T4), tốc độ 2 - 3 video/phút duy trì trong 10 phút (Tổng 25 video ngắn 15-30s).

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Pipeline SLA: Thời gian xử lý toàn trình (bao gồm độ trễ mạng Cloudflare Tunnel) p95 < 45 giây/video, Error Rate < 5%.  
• Colab Free SLA: GPU VRAM < 13.5 GB / 15 GB (Zero CUDA OOM), System RAM Colab < 11 GB / 12.7 GB, gọi torch.cuda.empty_cache() sau mỗi video.

**Điều kiện tiên quyết:**

Colab Free đã kết nối GPU Tesla T4, mở Cloudflare Tunnel ổn định; Các model AI đã load sẵn lên VRAM ở chế độ FP16/BF16.

**Round 1:**

**Passed**
- **Pipeline Latency**: p50 = `19.34 s`, p95 = `37.25 s` (`37245.21 ms`), Avg = `18.9 s`, Error Rate = `0.0%` (`6/6` videos)
- **Colab Free T4 (SSH `nvidia-smi`)**: GPU = `Tesla T4`, VRAM Peak = `3863.0 MB` (`3.77 GB / 15 GB`), GPU Util Peak = `94.0%`, Temp Peak = `61.0°C`, Colab System RAM Peak = `5.34 GB / 12.7 GB`

**Round 2:**

**Passed**
- **Pipeline Latency**: p50 = `0.28 s`, p95 = `1.05 s` (`1048.19 ms`), Avg = `0.45 s`, Error Rate = `0.0%` (`6/6` videos)
- **Colab Free T4 (SSH `nvidia-smi`)**: GPU = `Tesla T4`, VRAM Peak = `2615.0 MB` (`2.55 GB / 15 GB`), GPU Util Peak = `0.0%`, Temp Peak = `71.0°C`, Colab System RAM Peak = `4.37 GB / 12.7 GB`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Điều chỉnh quan trọng nhất: 50 tác vụ/phút là bất khả thi trên 1 GPU T4 Colab Free -> Hạ xuống 2-3 video/phút (concurrency 1-2)

---

#### TC_PERF_11 — Kiểm thử độ trễ đẩy thông báo thời gian thực qua WebSocket

**Loại kiểm thử:**

Load Test (WS)

**Mô tả kịch bản:**

Kiểm thử độ trễ đẩy thông báo thời gian thực qua WebSocket

**Quy trình & tham số thực thi:**

1. Giao thức: WS /ws/notifications (Duy trì 150 kết nối đồng thời trên máy local)  
2. Kịch bản tải: Phát 20 bản tin sự kiện/giây tới 150 WebSocket clients trong 3 phút.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: Độ trễ truyền tin p95 < 150 ms, Error Rate (rớt kết nối) = 0%.  
• Laptop SLA: Mức tiêu thụ RAM của 150 kết nối WebSocket (cả Server + Script test) < 300 MB.

**Điều kiện tiên quyết:**

150 kết nối WebSocket mở đồng thời từ công cụ k6 (chạy native binary trên Windows, không qua Docker).

**Round 1:**

**Passed**
- **WebSocket Connections**: `150/150` kết nối đồng thời (Dropped = `0`, Error Rate = `0.0%`)
- **Độ trễ truyền tin (Ping/Event)**: p50 = `3.88 ms`, p95 = `5.46 ms`, p99 = `6.33 ms`, RPS = `104.44 msg/s`
- **Hạ tầng Laptop**: WS RAM Delta = `39.88 MB`, CPU Avg = `15.44%`, RAM Avg = `90.4%`

**Round 2:**

**Passed**
- **WebSocket Connections**: `150/150` kết nối đồng thời (Dropped = `0`, Error Rate = `0.0%`)
- **Độ trễ truyền tin (Ping/Event)**: p50 = `4.56 ms`, p95 = `6.59 ms`, p99 = `7.78 ms`, RPS = `65.33 msg/s`
- **Hạ tầng Laptop**: WS RAM Delta = `154.42 MB`, CPU Avg = `17.95%`, RAM Avg = `89.87%`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Giảm từ 1.000 xuống 150 kết nối đồng thời để không tràn 575MB RAM trống của laptop

---

### NHÓM 3: Nhóm chức năng Xem chi tiết địa điểm, Video Review và Quản lý nội dung cá nhân

#### TC_PERF_12 — Kiểm thử tải xem chi tiết quán và danh sách video review liên quan

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải xem chi tiết quán và danh sách video review liên quan

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/places/{place_id}/detail-with-videos  
2. Kịch bản tải: Ramp-up 0 -> 80 VUs trong 30 giây; Duy trì 80 VUs, 35 req/giây trong 3 phút; Ramp-down 30 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 500 ms, Error Rate < 0,1%.  
• Laptop SLA: Truy vấn JOIN có phân trang phản hồi < 50 ms tại PostgreSQL.

**Điều kiện tiên quyết:**

Địa điểm đang hoạt động, có tối thiểu 20 video liên kết.

**Round 1:**

**Failed**
- **Client Metrics (Steady-state)**: Tổng `3389` reqs (Steady `2071` reqs, `45.62 req/s`) | p50 = `14.99 ms`, p95 = `387.62 ms`, p99 = `558.36 ms`, Avg = `61.73 ms`, Error Rate = `54.177%`
- **Laptop & Hạ tầng**: CPU Avg = `26.06%` (Peak `68.2%`), RAM Avg = `90.34%` (Min Free `588.0 MB`, RAM Delta `-54.7 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `place_videos_join_exec_ms=2.187`, `saved_places_join_exec_ms=2.995`, `saved_places_uses_index=True`, `db_deadlocks_count=0`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `4610` reqs (Steady `2472` reqs, `54.75 req/s`) | p50 = `8.45 ms`, p95 = `205.92 ms`, p99 = `408.25 ms`, Avg = `44.09 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `16.99%` (Peak `49.1%`), RAM Avg = `87.3%` (Min Free `608.93 MB`, RAM Delta `-176.95 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `place_videos_join_exec_ms=0.514`, `saved_places_join_exec_ms=3.669`, `saved_places_uses_index=True`, `db_deadlocks_count=0`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Hiệu chỉnh 80 VUs / 35 RPS trong 3 phút

---

#### TC_PERF_13 — Kiểm thử tải thao tác lưu và bỏ lưu địa điểm/video yêu thích

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải thao tác lưu và bỏ lưu địa điểm/video yêu thích

**Quy trình & tham số thực thi:**

1. Endpoint: POST & DELETE /api/v1/favorites  
2. Kịch bản tải: Ramp-up 0 -> 50 VUs trong 30 giây; Duy trì 50 VUs, 20 req/giây trong 3 phút; Ramp-down 30 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 350 ms, Error Rate < 0,1%.  
• Laptop SLA: Không xảy ra Deadlock khi ghi đồng thời vào bảng Favorites trên ổ SSD local.

**Điều kiện tiên quyết:**

Người dùng đã đăng nhập; Mã định danh video_id và place_id hợp lệ.

**Round 1:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `1710` reqs (Steady `1126` reqs, `24.79 req/s`) | p50 = `17.39 ms`, p95 = `292.44 ms`, p99 = `495.6 ms`, Avg = `62.29 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `19.73%` (Peak `56.3%`), RAM Avg = `90.1%` (Min Free `635.21 MB`, RAM Delta `36.73 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `deadlocks_before=0`, `deadlocks_after=0`, `new_deadlocks=0`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `2118` reqs (Steady `1227` reqs, `27.0 req/s`) | p50 = `16.16 ms`, p95 = `234.17 ms`, p99 = `620.46 ms`, Avg = `57.71 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `33.85%` (Peak `95.0%`), RAM Avg = `90.47%` (Min Free `608.29 MB`, RAM Delta `14.17 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `deadlocks_before=0`, `deadlocks_after=0`, `new_deadlocks=0`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Hiệu chỉnh 50 VUs / 20 RPS phù hợp I/O đĩa đơn trên laptop

---

#### TC_PERF_14 — Kiểm thử tải truy xuất, phân trang và lọc danh sách đã lưu

**Loại kiểm thử:**

Load Test

**Mô tả kịch bản:**

Kiểm thử tải truy xuất, phân trang và lọc danh sách đã lưu

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/favorites?category={cat}&page=1&limit=20  
2. Kịch bản tải: Ramp-up 0 -> 60 VUs trong 30 giây; Duy trì 60 VUs, 25 req/giây trong 3 phút; Ramp-down 30 giây.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Client SLA: p95 < 600 ms, Error Rate < 0,1%.  
• Laptop SLA: Sử dụng đúng Composite Index, không quét toàn bảng.

**Điều kiện tiên quyết:**

Mỗi tài khoản kiểm thử có sẵn tối thiểu 100 bản ghi đã lưu.

**Round 1:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `2123` reqs (Steady `1383` reqs, `30.48 req/s`) | p50 = `21.06 ms`, p95 = `402.47 ms`, p99 = `460.34 ms`, Avg = `76.38 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `19.11%` (Peak `49.5%`), RAM Avg = `89.55%` (Min Free `731.02 MB`, RAM Delta `-139.88 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `place_videos_join_exec_ms=0.36`, `saved_places_join_exec_ms=0.542`, `saved_places_uses_index=True`, `db_deadlocks_count=0`

**Round 2:**

**Passed**
- **Client Metrics (Steady-state)**: Tổng `2631` reqs (Steady `1515` reqs, `33.18 req/s`) | p50 = `16.69 ms`, p95 = `404.79 ms`, p99 = `903.17 ms`, Avg = `74.7 ms`, Error Rate = `0.0%`
- **Laptop & Hạ tầng**: CPU Avg = `26.12%` (Peak `73.6%`), RAM Avg = `89.39%` (Min Free `678.48 MB`, RAM Delta `-394.16 MB`)
- **Thông số DB/Cache/Hạ tầng bổ sung**: `place_videos_join_exec_ms=0.453`, `saved_places_join_exec_ms=0.511`, `saved_places_uses_index=True`, `db_deadlocks_count=0`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Hiệu chỉnh 60 VUs / 25 RPS trong 3 phút

---

#### TC_PERF_15 — Kiểm thử hiệu năng kết xuất bản đồ (Map Rendering) và phát video trên trình duyệt

**Loại kiểm thử:**

Client Performance

**Mô tả kịch bản:**

Kiểm thử hiệu năng kết xuất bản đồ (Map Rendering) và phát video trên trình duyệt

**Quy trình & tham số thực thi:**

1. Thao tác: 1 người dùng thao tác pan/zoom bản đồ 150 markers và mở phát video liên tục trong 5 phút trên trình duyệt Brave/Chrome.  
2. Công cụ đo: Chrome/Brave DevTools Performance (chạy trực tiếp trên GPU tích hợp Intel UHD/Iris Xe của MSI Modern 14).

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Tải bản đồ lần đầu < 2,5 giây; Phát video < 1,5 giây; Tỷ lệ lỗi = 0%.  
• Tốc độ khung hình khi di chuyển bản đồ đạt >= 45 FPS; Tab trình duyệt chiếm RAM < 400 MB.

**Điều kiện tiên quyết:**

Chỉ mở duy nhất 1 tab ứng dụng đang kiểm thử để tránh thiếu hụt RAM hệ thống.

**Round 1:**

**Failed**
- **Tải bản đồ & Phát video**: Tải bản đồ lần đầu = `2702.57 ms` (`2.7 s`, SLO `< 2.5 s`, `50` markers) | Phát/chuyển video (`18` lượt): p50 = `396.73 ms`, p95 = `2250.11 ms` (SLO `< 1,500 ms`), Max = `7969.34 ms`, Error Rate = `0.0%`
- **Tốc độ khung hình (Pan/Zoom FPS) & Bộ nhớ Tab (Chrome CDP)**: FPS Avg = `26.6 FPS` (p50 = `23.8 FPS`, Min = `0.8 FPS`, Max = `60 FPS`, SLO `>= 45 FPS`) | Tab Renderer RAM Peak = `682.1 MB` (Avg = `594.59 MB`, SLO `< 400 MB`), JS Heap Peak = `172.32 MB` (Tri-Buffer max `3` iframes)
- **Laptop & GPU tích hợp**: GPU = `ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x00009A49) Direct3D11 vs_5_0 ps_5_0, D3D11)`, Single Tab = `True` | CPU Avg = `64.32%` (Peak `97.2%`), RAM Avg = `90.83%` (Min Free `492.6 MB`)

**Round 2:**

Pending

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Đo trực tiếp trên đồ họa tích hợp của laptop MSI Modern 14 trong 5 phút

---

### NHÓM 4: Nhóm chức năng Kiểm thử Ngưỡng giới hạn (Stress Test) và Chịu lỗi Kết nối Colab

#### TC_PERF_16 — Kiểm thử tìm ngưỡng giới hạn (Breaking Point) trên Laptop 8GB RAM

**Loại kiểm thử:**

Stress Test

**Mô tả kịch bản:**

Kiểm thử tìm ngưỡng giới hạn (Breaking Point) trên Laptop 8GB RAM

**Quy trình & tham số thực thi:**

1. Endpoint: GET /api/v1/places/within-radius  
2. Kịch bản tải: Tăng bậc thang từ 50 -> 100 -> 150 -> 200 -> 250 VUs (mỗi bậc 1 phút) cho đến khi p95 > 2.000 ms hoặc RAM hệ thống chạm mức 95%.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Xác định ngưỡng tải tối đa thực tế của máy local (dự kiến khoảng 150 - 200 VUs).  
• Hệ thống tự hồi phục về p95 < 500 ms sau khi ngừng bắn tải mà không làm sập tiến trình PostgreSQL/FastAPI.

**Điều kiện tiên quyết:**

Mở sẵn Task Manager / Resource Monitor để quan sát ngưỡng bão hòa CPU và RAM.

**Round 1:**

**Failed**
- **Kết quả từng bậc tải**: `50 VUs`: p95=`10016.53ms`, Err=`51.429%`, RAM=`90.2%` | `100 VUs`: p95=`10019.39ms`, Err=`100.0%`, RAM=`89.7%` | `150 VUs`: p95=`10020.67ms`, Err=`100.0%`, RAM=`89.0%` | `200 VUs`: p95=`10028.47ms`, Err=`100.0%`, RAM=`88.1%` | `250 VUs`: p95=`10028.88ms`, Err=`100.0%`, RAM=`87.7%`
- **Ngưỡng giới hạn (Breaking Point)**: `50` (p95=10016.53ms (>2000ms) hoặc RAM=90.2% (>=95%))
- **Khả năng tự hồi phục (Recovery)**: p95 = `10016.29 ms`, Services Alive = `False`

**Round 2:**

**Passed**
- **Kết quả từng bậc tải**: `50 VUs`: p95=`297.25ms`, Err=`0.0%`, RAM=`87.3%` | `100 VUs`: p95=`780.2ms`, Err=`0.0%`, RAM=`90.6%` | `150 VUs`: p95=`708.22ms`, Err=`0.0%`, RAM=`90.5%` | `200 VUs`: p95=`857.73ms`, Err=`0.0%`, RAM=`90.5%` | `250 VUs`: p95=`2490.9ms`, Err=`0.0%`, RAM=`89.4%`
- **Ngưỡng giới hạn (Breaking Point)**: `250` (p95=2490.9ms (>2000ms) hoặc RAM=89.4% (>=95%))
- **Khả năng tự hồi phục (Recovery)**: p95 = `82.69 ms`, Services Alive = `True`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Tìm ngưỡng gãy thực tế của cấu hình 8GB RAM (50 -> 250 VUs)

---

#### TC_PERF_17 — Kiểm thử cơ chế xếp hàng (Backpressure) khi đẩy 30 video liên tiếp về Colab Free

**Loại kiểm thử:**

Stress Test (Queue)

**Mô tả kịch bản:**

Kiểm thử cơ chế xếp hàng (Backpressure) khi đẩy 30 video liên tiếp về Colab Free

**Quy trình & tham số thực thi:**

1. Endpoint: POST /api/v1/videos/analyze  
2. Kịch bản tải: Gửi dồn dập 30 yêu cầu phân tích video trong 30 giây để kiểm tra hàng đợi bảo vệ GPU Colab.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• API tiếp nhận trả về HTTP 202 dưới 500 ms cho cả 30 request.  
• Worker trên Colab chỉ lấy từng task (concurrency = 1 hoặc 2) từ hàng đợi để xử lý tuần tự, tuyệt đối không nhận 30 task cùng lúc gây sập Colab (CUDA OOM).

**Điều kiện tiên quyết:**

Cấu hình Celery/Worker prefetch_multiplier = 1 và max_concurrency = 1 trên Colab.

**Round 1:**

**Passed**
- **Tiếp nhận 30 videos (HTTP 202)**: `30/30` thành công | p50 = `84.39 ms`, p95 = `176.18 ms`, Max = `178.52 ms`, Error Rate = `0.0%`
- **Backpressure & Hàng đợi Redis**: Peak Queue Depth = `15` tasks | Worker Concurrency thực tế (`status=PROCESSING`) = `2` task
- **Colab Free T4 (SSH `nvidia-smi`)**: VRAM Peak = `2615.0 MB` (`2.55 GB / 15 GB`, Zero CUDA OOM), Colab RAM Peak = `5.27 GB`

**Round 2:**

**Passed**
- **Tiếp nhận 30 videos (HTTP 202)**: `30/30` thành công | p50 = `67.73 ms`, p95 = `101.16 ms`, Max = `104.89 ms`, Error Rate = `0.0%`
- **Backpressure & Hàng đợi Redis**: Peak Queue Depth = `6` tasks | Worker Concurrency thực tế (`status=PROCESSING`) = `2` task
- **Colab Free T4 (SSH `nvidia-smi`)**: VRAM Peak = `2615.0 MB` (`2.55 GB / 15 GB`, Zero CUDA OOM), Colab RAM Peak = `4.38 GB`

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Kiểm chứng cơ chế bảo vệ Colab Free không bị văng Runtime khi dồn task

---

#### TC_PERF_18 — Kiểm thử khả năng chịu lỗi khi Cloudflare Tunnel / Colab Free bị ngắt kết nối đột ngột

**Loại kiểm thử:**

Failover Test

**Mô tả kịch bản:**

Kiểm thử khả năng chịu lỗi khi Cloudflare Tunnel / Colab Free bị ngắt kết nối đột ngột

**Quy trình & tham số thực thi:**

1. Endpoint: POST /api/v1/videos/analyze & GET /api/v1/places/within-radius  
2. Kịch bản tải: Đang chạy tải 30 VUs thì chủ động ngắt kết nối Cloudflare Tunnel tới Colab Free trong 1 phút.

**Kết quả kỳ vọng: SLA & hạ tầng:**

• Các tác vụ phân tích video tự động chuyển sang trạng thái RETRY/PENDING trong Queue (không mất task), trả thông báo rõ ràng cho người dùng.  
• Các chức năng bản đồ và xem quán trên Laptop vẫn hoạt động bình thường (p95 < 600 ms, Error Rate = 0%).

**Điều kiện tiên quyết:**

Backend FastAPI đã cấu hình Timeout (10s) và xử lý ngoại lệ khi gọi sang AI Server qua Cloudflare Tunnel.

**Round 1:**

**Failed**
- **Luồng Bản đồ (`GET /api/v1/places/nearby-videos`) khi đứt Tunnel**: `372` reqs | p50 = `55.92 ms`, p95 = `744.58 ms`, Error Rate = `1.613%`
- **Luồng Gửi Video (`POST /api/v1/videos/submit`) khi đứt Tunnel**: `62` reqs | HTTP 202 p95 = `20004.74 ms`, Error Rate tiếp nhận = `11.29%`
- **Phát hiện thực tế tại Worker**: Khi Tunnel ngắt kết nối, API tiếp nhận vẫn trả 202 Accepted và giữ task trong Redis/DB; Worker khi rút task gặp lỗi kết nối sẽ chuyển trạng thái sang FAILED kèm error_message và bắn WebSocket FAILED (hiện tại code analysis_service.py gọi fail_analysis() chứ chưa có cơ chế tự động RETRY). Đồng thời AI_REQUEST_TIMEOUT trong config.py đang là 180s thay vì 10s.

**Round 2:**

**Passed**
- **Luồng Bản đồ (`GET /api/v1/places/nearby-videos`) khi đứt Tunnel**: `672` reqs | p50 = `10.14 ms`, p95 = `145.61 ms`, Error Rate = `0.0%`
- **Luồng Gửi Video (`POST /api/v1/videos/submit`) khi đứt Tunnel**: `112` reqs | HTTP 202 p95 = `200.26 ms`, Error Rate tiếp nhận = `0.0%`
- **Phát hiện thực tế tại Worker**: Khi Tunnel ngắt kết nối, API tiếp nhận vẫn trả 202 Accepted và giữ task trong Redis/DB; Worker phát hiện lỗi kết nối trong vòng < 10s (connect=10.0s), tự động chuyển trạng thái sang RETRY kèm thông báo WebSocket RETRY và đẩy lại vào hàng đợi Redis để xử lý lại khi có mạng.

**Round 3:**

Pending

**Ghi chú hiệu chỉnh:**

Đặc thù cho kiến trúc dùng Colab Free (rất hay bị ngắt kết nối)

---
