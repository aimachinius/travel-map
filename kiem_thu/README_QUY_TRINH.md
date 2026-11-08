# Quy Trình Kiểm Thử Hiệu Năng & Hướng Dẫn Thực Thi (`kiem_thu`)

Tài liệu này mô tả toàn bộ cấu trúc thư mục, quy trình chuẩn bị dữ liệu, cách vận hành bộ script kiểm thử hiệu năng tự động, vị trí lưu trữ log thực tế và hướng dẫn kiểm thử thủ công cho `TC_PERF_15`.

---

## 1. Cấu Trúc Thư Mục `kiem_thu/`

```text
kiem_thu/
├── performance_testing.md               # Tài liệu đặc tả & kết quả kiểm thử (Đã cập nhật Round 1)
├── README_QUY_TRINH.md                  # Tài liệu quy trình & hướng dẫn sử dụng (File này)
├── data/
│   ├── users_200.csv                    # 200 tài khoản kiểm thử (user_id, username, email, password, access_token)
│   └── seeded_ids.json                  # Metadata ID đã seed (users, places >= 20 videos, completed runs)
├── logs/
│   ├── ai_server_ssh_audit.log          # Log kiểm tra SSH ban đầu tới Google Colab Tesla T4
│   ├── ssh_TC_PERF_10.log               # Log nvidia-smi VRAM & RAM trên Colab trong suốt bài test TC_PERF_10
│   └── ssh_TC_PERF_17.log               # Log nvidia-smi VRAM & RAM trên Colab trong suốt bài test TC_PERF_17
├── results/
│   ├── env_audit.json                   # Thông số kiểm tra môi trường Host, Docker, PostgreSQL, Redis, Tunnel, SSH
│   ├── summary_report.md                # Báo cáo tổng hợp kết quả Round 1 & Phân tích 5 nút cổ chai hệ thống
│   └── round_1/
│       ├── TC_PERF_01.json              # Kết quả chi tiết TC_PERF_01
│       ├── TC_PERF_04.json              # Kết quả chi tiết TC_PERF_04
│       ├── TC_PERF_05.json              # Kết quả chi tiết TC_PERF_05
│       ├── TC_PERF_06.json              # Kết quả chi tiết TC_PERF_06
│       ├── TC_PERF_07.json              # Kết quả chi tiết TC_PERF_07
│       ├── TC_PERF_08.json              # Kết quả chi tiết TC_PERF_08
│       ├── TC_PERF_09.json              # Kết quả chi tiết TC_PERF_09
│       ├── TC_PERF_10.json              # Kết quả chi tiết TC_PERF_10 (Kèm chi tiết 6 video & metrics AI)
│       ├── TC_PERF_11.json              # Kết quả chi tiết TC_PERF_11 (150 kết nối WebSocket)
│       ├── TC_PERF_12.json              # Kết quả chi tiết TC_PERF_12
│       ├── TC_PERF_13.json              # Kết quả chi tiết TC_PERF_13
│       ├── TC_PERF_14.json              # Kết quả chi tiết TC_PERF_14
│       ├── TC_PERF_16.json              # Kết quả chi tiết TC_PERF_16 (Breaking Point Stress Test)
│       ├── TC_PERF_17.json              # Kết quả chi tiết TC_PERF_17 (Backpressure 30 videos + Queue timeline)
│       └── TC_PERF_18.json              # Kết quả chi tiết TC_PERF_18 (Failover khi đứt Cloudflare Tunnel)
└── scripts/
    ├── env_check.py                     # Kiểm tra môi trường Host, Docker, DB, Redis, Tunnel & SSH AI Server
    ├── seed_perf_data.py                # Seed 500 users, 10.000 places Đà Nẵng, >= 500 videos COMPLETED, >= 100 saved/user
    ├── perf_engine.py                   # Core Async Load Testing Engine + Host/SSH Telemetry Monitor
    ├── run_group0_auth.py               # Thực thi TC_PERF_01, TC_PERF_04
    ├── run_group1_map.py                # Thực thi TC_PERF_05, TC_PERF_06, TC_PERF_07
    ├── run_group2_video_ws.py           # Thực thi TC_PERF_08, TC_PERF_09, TC_PERF_10, TC_PERF_11
    ├── run_group3_places_saved.py       # Thực thi TC_PERF_12, TC_PERF_13, TC_PERF_14
    ├── run_group4_stress_failover.py    # Thực thi TC_PERF_16, TC_PERF_17, TC_PERF_18
    └── generate_report.py               # Tự động cập nhật kết quả từ JSON vào performance_testing.md
```

---

## 2. Quy Trình Thực Thi Từng Bước

### Bước 1: Kiểm tra môi trường & kết nối AI Server
```powershell
python kiem_thu/scripts/env_check.py
```
- Kiểm tra CPU/RAM của Laptop, trạng thái 5 container Docker (`foodspot-db`, `foodspot-redis`, `foodspot-backend`, `foodspot-mock-ai`, `foodspot-front`), cấu hình PostgreSQL & GIST Index, Cloudflare Tunnel và SSH tới Server AI.

### Bước 2: Khởi tạo dữ liệu kiểm thử (Seeding)
```powershell
python kiem_thu/scripts/seed_perf_data.py
```
- Tạo đủ `500` tài khoản test và xuất 200 tài khoản ra [`kiem_thu/data/users_200.csv`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/data/users_200.csv).
- Tạo đủ `10.000+` địa điểm (`places`) có tọa độ PostGIS `POINT(lon lat)` tại Đà Nẵng kèm lưới `discovery_scans` để ngăn việc kích hoạt nhầm tiến trình Playwright cào TikTok ngầm trong lúc bắn tải bản đồ.
- Tạo đủ `600` videos, `20` địa điểm có `>= 25` videos liên kết, và `110` bản ghi đã lưu cho mỗi tài khoản test.

### Bước 3: Chạy các nhóm kịch bản kiểm thử
Có thể điều chỉnh tham số `--scale` (`1.0` để chạy 100% thời lượng gốc hoặc `0.25` để chạy nhanh):
```powershell
# Nhóm 0: Xác thực & Spike Test (TC_PERF_01, TC_PERF_04)
python kiem_thu/scripts/run_group0_auth.py --scale 0.25

# Nhóm 1: Tìm kiếm Geocoding & Quét bán kính PostGIS (TC_PERF_05, TC_PERF_06, TC_PERF_07)
python kiem_thu/scripts/run_group1_map.py --scale 0.20

# Nhóm 2: Video Queue, AI Pipeline Colab T4 & WebSocket 150 Conns (TC_PERF_08..11)
python kiem_thu/scripts/run_group2_video_ws.py --scale 0.25 --ai-videos 6

# Nhóm 3: Chi tiết quán & Danh sách yêu thích (TC_PERF_12..14)
python kiem_thu/scripts/run_group3_places_saved.py --scale 0.25

# Nhóm 4: Stress Breaking Point, Backpressure 30 Videos & Failover (TC_PERF_16..18)
python kiem_thu/scripts/run_group4_stress_failover.py --scale 0.25
```

### Bước 4: Cập nhật kết quả vào bảng `performance_testing.md`
```powershell
python kiem_thu/scripts/generate_report.py
```

---

## 3. Hướng Dẫn Tự Kiểm Thử Thủ Công Cho `TC_PERF_15`

Theo yêu cầu, `TC_PERF_15` (*Kiểm thử hiệu năng kết xuất bản đồ Map Rendering và phát video trên trình duyệt*) được giữ ở trạng thái `Pending` để bạn trực tiếp đo trên trình duyệt Chrome/Brave:

1. Mở duy nhất 1 tab trình duyệt Chrome hoặc Brave truy cập `http://localhost:5173`.
2. Đăng nhập bằng tài khoản test (ví dụ: `perf_user_0001@foodspot.test` / mật khẩu `Password123!`).
3. Nhấn `F12` mở **DevTools**:
   - Mở tab **Performance**, tích chọn **Memory** và bấm nút **Record**.
   - Nhấn `Ctrl + Shift + P` $\rightarrow$ gõ `Show frames per second (FPS) meter` để bật đồng hồ đo FPS trực tiếp trên góc màn hình.
4. Thực hiện thao tác kéo/thả (pan), phóng to/thu nhỏ (zoom) bản đồ tại khu vực Đà Nẵng (nơi đã được seed sẵn dữ liệu địa điểm và video) và bấm mở phát video review trong 5 phút.
5. Dừng **Record** và ghi nhận 4 chỉ số vào mục **Round 1** của `TC_PERF_15` trong [`kiem_thu/performance_testing.md`](file:///d:/year_4/pbl/team_repo/travel-map/kiem_thu/performance_testing.md):
   - Thời gian tải bản đồ lần đầu (SLA: `< 2,5 giây`)
   - Thời gian bắt đầu phát video (SLA: `< 1,5 giây`)
   - Tốc độ khung hình khi pan/zoom (SLA: `>= 45 FPS`)
   - Dung lượng RAM của tab trình duyệt trong Chrome Task Manager `Shift + Esc` (SLA: `< 400 MB`)

