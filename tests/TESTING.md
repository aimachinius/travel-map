# 🧪 TÀI LIỆU HƯỚNG DẪN KIỂM THỬ TOÀN DIỆN (AI SERVER TESTING GUIDE)

Tài liệu này cung cấp toàn bộ hướng dẫn, kịch bản và câu lệnh kiểm thử cho hệ thống **Restaurant Extraction AI Server**, bao gồm cả kiểm thử đơn vị độc lập từng module và kiểm thử trực tiếp các API endpoint qua lệnh `curl` (cả cổng nội bộ Local và cầu nối công khai Cloudflare Tunnel).

---

## 1. Bản Đồ Các Module Kiểm Thử Độc Lập

Hệ thống được thiết kế theo kiến trúc Module hóa cao độ, cho phép kiểm thử từng thành phần tách biệt mà không phụ thuộc vào toàn bộ server:

| Tên Module | File Test Tương Ứng | Mục Tiêu & Kịch Bản Kiểm Thử |
| :--- | :--- | :--- |
| **`downloader`** | [`test_downloader.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/test_downloader.py) | Kiểm thử tải video TikTok / YouTube Shorts qua `yt-dlp`, cơ chế bắt lỗi URL hỏng, và cơ chế cache bỏ qua tải lại. |
| **`vision`** | [`test_vision_detector.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/test_vision_detector.py) | Kiểm thử `FastSinglePassSampler` ($64\times 64$ diff), `GPUDBNetDetector` (CUDA + CPU fallback, max_side=640, mini-batch), chọn keyframe biển hiệu. |
| **`vlm`** | [`test_vlm_extractor.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/test_vlm_extractor.py) | Kiểm thử Pure Vision 3 bước, Majority Voting, Fast-Path bypass, chống ảo giác ("BẮT BUỘC", "10.75%"), thẩm định địa chỉ (`validate_address_entities`). |
| **`storage`** | [`test_storage_manager.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/test_storage_manager.py) | Kiểm thử lưu/đọc Cache MD5, dọn dẹp file tạm TTL 24h và cơ chế xóa an toàn không xung đột tiến trình. |
| **`tunnel`** | [`test_tunnel_manager.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/test_tunnel_manager.py) | Kiểm thử khởi tạo cấu hình cầu nối Cloudflare Tunnel, Ngrok và chế độ chỉ mở cổng nội bộ (local-only). |
| **`pipeline`** | [`test_server_pipeline.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/test_server_pipeline.py) | Kiểm thử liên kết luồng Pure Vision End-to-End từ URL đầu vào đến JSON kết quả mà không cần khởi động HTTP server. |
| **`api`** | [`test_api_endpoints.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/test_api_endpoints.py) | Kiểm thử toàn bộ REST API FastAPI qua `TestClient`: `/health`, `/extract`, `/jobs`, và các mã lỗi 400, 404, 500. |

---

## 2. Hướng Dẫn Chạy Test Bằng Python CLI Runner

Hệ thống tích hợp sẵn CLI Test Runner tập trung tại [`src/tests/run_tests.py`](file:///g:/マイドライブ/colab/pbl/main/src/tests/run_tests.py).

### 2.1. Chạy Toàn Bộ 7 Module Cùng Lúc
```bash
python src/tests/run_tests.py --module all
```
*Kết quả mẫu đạt chuẩn:*
```text
=================================================================
📊 [TỔNG KẾT KẾT QUẢ KIỂM THỬ TOÀN HỆ THỐNG (v3.0 PURE VISION)]
=================================================================
  - Module downloader  : ✅ PASSED
  - Module vision      : ✅ PASSED
  - Module vlm         : ✅ PASSED
  - Module storage     : ✅ PASSED
  - Module tunnel      : ✅ PASSED
  - Module pipeline    : ✅ PASSED
  - Module api         : ✅ PASSED
-----------------------------------------------------------------
Tổng thời gian: ~12s | Trạng thái chung: ✅ TẤT CẢ MODULE ĐẠT
=================================================================
```

### 2.2. Chạy Riêng Lẻ Từng Module Cần Kiểm Tra
```bash
# Kiểm thử riêng Module tải video
python src/tests/run_tests.py --module downloader

# Kiểm thử riêng Module Thị giác máy tính & Lấy mẫu nhanh
python src/tests/run_tests.py --module vision

# Kiểm thử riêng Module Prompt & Thẩm định thực thể VLM
python src/tests/run_tests.py --module vlm

# Kiểm thử riêng Module Quản lý Lưu trữ & Cache
python src/tests/run_tests.py --module storage

# Kiểm thử riêng Module Quản lý Cầu nối Mạng (Tunnel)
python src/tests/run_tests.py --module tunnel

# Kiểm thử riêng Module Pipeline tổng hợp
python src/tests/run_tests.py --module pipeline

# Kiểm thử riêng Module API Endpoints
python src/tests/run_tests.py --module api
```

---

## 3. Bộ Kịch Bản Kiểm Thử Thực Tế Bằng `curl`

Khi máy chủ đang chạy:
- **Cổng nội bộ (Local):** `http://127.0.0.1:8000`
- **Cầu nối công khai (Public):** `https://<subdomain>.trycloudflare.com` *(lấy từ log khởi động)*

> 💡 **Mẹo:** Trong các lệnh bên dưới, bạn có thể thay thế `http://127.0.0.1:8000` bằng URL Cloudflare công khai của mình khi gọi từ máy ngoài hoặc trình duyệt.

---

### Kịch Bản 1: Kiểm Tra Trạng Thái Sức Khỏe & VRAM Máy Chủ (`/health`)

**Lệnh cURL:**
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/health" \
     -H "Accept: application/json"
```

**Hoặc dùng endpoint alias rút gọn:**
```bash
curl -X GET "http://127.0.0.1:8000/health"
```

**Phản hồi kỳ vọng (200 OK):**
```json
{
  "status": "HEALTHY",
  "access_urls": {
    "local_url": "http://127.0.0.1:8000",
    "public_tunnel_url": "https://deeply-dawn-separated-pension.trycloudflare.com",
    "tunnel_provider": "cloudflare",
    "is_tunnel_active": true
  },
  "gpu_available": true,
  "gpu_name": "Tesla T4",
  "vram_used_mb": 4210.5,
  "vram_total_mb": 15109.0,
  "models_loaded": {
    "dbnet_onnx": true,
    "phowhisper_medium": true,
    "vintern_1b": true
  }
}
```

---

### Kịch Bản 2: Gửi Yêu Cầu Trích Xuất Trực Tiếp Đồng Bộ (`/extract`)

Endpoint này sẽ tải video, chạy ASR, cắt khung hình, gọi VLM và trả về kết quả đầy đủ trong cùng 1 request HTTP (phù hợp cho các client chấp nhận chờ 8–15s).

#### A. Trích xuất video TikTok:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/extract" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://www.tiktok.com/@review_an_ngon/video/7328912345678901234",
       "force_reload": false
     }'
```

#### B. Trích xuất video YouTube Shorts:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/extract" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://www.youtube.com/shorts/kJQP7kiw5Fk",
       "force_reload": false
     }'
```

**Phản hồi kỳ vọng (200 OK):**
```json
{
  "success": true,
  "status": "SUCCESS",
  "data": {
    "restaurant": {
      "name": "Bún Bò Huế Bà Gái",
      "address": "47 Bà Triệu, Phường Phú Hội, Thành phố Huế",
      "confidence": "HIGH"
    },
    "keyframes": [
      {
        "frame_index": 3,
        "filename": "keyframe_0_3.jpg",
        "url": "/api/v1/keyframes/keyframe_0_3.jpg",
        "score": 0.892,
        "text_boxes_count": 4
      }
    ],
    "video_metadata": {
      "video_id": "7328912345678901234",
      "platform": "tiktok",
      "duration": 42.5,
      "width": 720,
      "height": 1280
    },
    "transcription": {
      "script": "Hôm nay mình dẫn các bạn đi ăn quán bún bò huế bà gái nằm ở số 47 đường bà triệu...",
      "duration_sec": 42.0
    },
    "execution_time_sec": 9.42,
    "cached": false
  },
  "error_code": null,
  "error_message": null
}
```

---

### Kịch Bản 3: Gửi Tác Vụ Trích Xuất Nền Bất Đồng Bộ (`/jobs`)

Dành cho hệ thống quy mô lớn hoặc client trên mobile muốn tránh timeout HTTP:

#### Bước 3.1: Tạo Job
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://www.youtube.com/shorts/kJQP7kiw5Fk"
     }'
```

**Phản hồi kỳ vọng (202 Accepted):**
```json
{
  "job_id": "job_046487c3e080",
  "status": "QUEUED",
  "message": "Tác vụ đã được tiếp nhận và đang xếp hàng xử lý."
}
```

#### Bước 3.2: Thăm dò (Polling) Trạng Thái Job
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/jobs/job_046487c3e080"
```

**Khi đang xử lý (200 OK):**
```json
{
  "job_id": "job_046487c3e080",
  "url": "https://www.youtube.com/shorts/kJQP7kiw5Fk",
  "status": "TRANSCRIBING",
  "created_at": 1729952000.0,
  "updated_at": 1729952003.5,
  "result": null,
  "error_message": null
}
```

**Khi hoàn thành (200 OK):**
```json
{
  "job_id": "job_046487c3e080",
  "url": "https://www.youtube.com/shorts/kJQP7kiw5Fk",
  "status": "COMPLETED",
  "created_at": 1729952000.0,
  "updated_at": 1729952011.2,
  "result": {
    "restaurant": {
      "name": "Phở Gia Truyền Bát Đàn",
      "address": "49 Bát Đàn, Cửa Đông, Hoàn Kiếm, Hà Nội",
      "confidence": "HIGH"
    }
  },
  "error_message": null
}
```

---

### Kịch Bản 4: Xem Danh Sách Các Tác Vụ Gần Đây

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/jobs?limit=5"
```

---

### Kịch Bản 5: Tải / Xem Trực Tiếp Ảnh Keyframe Biển Hiệu Quán

```bash
# Tải ảnh keyframe về máy
curl -O "http://127.0.0.1:8000/api/v1/keyframes/keyframe_0_3.jpg"
```

---

### Kịch Bản 6: Kiểm Thử Các Ca Biên (Edge Cases & Error Handling)

#### A. Gửi URL Rỗng (Kiểm tra validation 400 Bad Request):
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/extract" \
     -H "Content-Type: application/json" \
     -d '{"url": ""}'
```
*Kỳ vọng:* `HTTP 400: URL video không được để trống.`

#### B. Gửi URL từ nền tảng không hỗ trợ (Facebook, Twitter):
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/extract" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.facebook.com/watch/?v=987654321"}'
```
*Kỳ vọng:* `HTTP 400: Nền tảng video không được hỗ trợ. Chỉ hỗ trợ video từ TikTok và YouTube Shorts.`

#### C. Truy vấn Job không tồn tại:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/jobs/job_khong_ton_tai_9999"
```
*Kỳ vọng:* `HTTP 404: Không tìm thấy job_id này.`

---

## 4. Kiểm Thử Bằng Python Script (`requests`)

Nếu bạn muốn viết script tự động hóa kiểm thử gọi API từ máy tính hoặc dịch vụ khác:

```python
import requests
import json
import time

SERVER_URL = "http://127.0.0.1:8000"  # Hoặc https://*.trycloudflare.com

# 1. Kiểm tra Health
res_health = requests.get(f"{SERVER_URL}/api/v1/health")
print("Health Status:", res_health.json()["status"])

# 2. Gửi tác vụ Async Job
payload = {"url": "https://www.youtube.com/shorts/kJQP7kiw5Fk"}
res_job = requests.post(f"{SERVER_URL}/api/v1/jobs", json=payload)
job_id = res_job.json()["job_id"]
print(f"Đã tạo Job: {job_id}")

# 3. Chờ và kiểm tra trạng thái
for _ in range(30):
    time.sleep(2)
    info = requests.get(f"{SERVER_URL}/api/v1/jobs/{job_id}").json()
    status = info["status"]
    print(f"Trạng thái Job: {status}")
    if status in ["COMPLETED", "FAILED"]:
        print("Kết quả:", json.dumps(info.get("result"), indent=2, ensure_ascii=False))
        break
```

---
*Tài liệu kiểm thử được cập nhật và duy trì tại:* [`src/tests/TESTING.md`](file:///g:/マイドライブ/colab/pbl/main/src/tests/TESTING.md)
