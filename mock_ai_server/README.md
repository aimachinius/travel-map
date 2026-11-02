# Food Spot - Mock AI Extraction Server

Server mô phỏng pipeline AI phục vụ kiểm thử hệ thống Food Spot:
- Nhận request phân tích video review (`POST /api/v1/extract`).
- Giả lập thời gian xử lý video và trả về kết quả địa điểm ẩm thực ngẫu nhiên tại **Đà Nẵng** (Bún chả cá Bà Lữ, Mì Quảng Bà Mua, Bánh Xèo Bà Dưỡng, Cơm Gà A Hải, v.v.).
- Trả về cấu trúc JSON chuẩn xác theo đúng khế ước mong đợi của Backend `AnalysisService`.

---

## 1. Cách khởi động Mock Server

### Cách 1: Chạy trực tiếp bằng Python (Khuyên dùng khi dev)

Mở terminal tại thư mục `mock_ai_server`:
```powershell
cd d:\year_4\pbl\team_repo\travel-map\mock_ai_server

# Cài thư viện (nếu chưa có)
pip install -r requirements.txt

# Khởi chạy server trên cổng 8001
python main.py
```
Server sẽ chạy tại: `http://localhost:8001` (Kiểm tra tại `http://localhost:8001/health`).

---

### Cách 2: Chạy bằng Docker

```powershell
cd d:\year_4\pbl\team_repo\travel-map\mock_ai_server
docker build -t mock-ai-server .
docker run -d --name foodspot-mock-ai -p 8001:8001 mock-ai-server
```

---

## 2. Cấu hình Backend kết nối với Mock Server

Mở file [`backend/.env`](file:///d:/year_4/pbl/team_repo/travel-map/backend/.env) (hoặc thiết lập biến môi trường) để trỏ đến Mock Server:

### Trường hợp 1: Backend chạy trực tiếp ngoài máy host (`uvicorn app.main:app`)
```env
AI_SERVER_EXTRACT_URL=http://localhost:8001/api/v1/extract
AI_REQUEST_TIMEOUT=180
```

### Trường hợp 2: Backend chạy trong Docker container (`docker compose up`)
Vì backend chạy bên trong container, để kết nối ra máy host cổng `8001`, sử dụng `host.docker.internal`:
```env
AI_SERVER_EXTRACT_URL=http://host.docker.internal:8001/api/v1/extract
AI_REQUEST_TIMEOUT=180
```
Sau đó khởi động lại backend:
```powershell
docker compose up -d backend
```

---

## 3. Kiểm thử API thủ công qua curl hoặc PowerShell

Gửi request phân tích video thử nghiệm:

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/extract" -Method Post -ContentType "application/json" -Body '{"url": "https://www.tiktok.com/@foodreview/video/123456789"}'
```

Output trả về:
```json
{
  "success": true,
  "status": "SUCCESS",
  "data": {
    "restaurant": {
      "name": "HongKong Style",
      "address": "181 Nguyễn Văn Thoại, Đà Nẵng",
      "confidence_status": "Cao",
      "evidence": {
        "name_source": "Frame 3, Frame 5 (OCR)",
        "address_source": "Frame 1, Frame 4 (OCR)"
      },
      "evidence_sources": [
        "Frame 3, Frame 5 (OCR)",
        "Frame 1, Frame 4 (OCR)"
      ]
    },
    "frames_ocr_details": [
      {
        "frame_idx": 110,
        "temporal_zone": "intro",
        "timestamp_sec": 3.67,
        "final_score": 1.7654,
        "image_url": "/api/v1/keyframes/7699467006587751688/frame_00.jpg",
        "ocr_name": "Dim Sum Ký",
        "ocr_address": "181 Nguyễn Văn Thoại, Đà Nẵng",
        "ocr_other": null
      }
    ],
    "video": {
      "video_id": "7699467006587751688",
      "platform": "tiktok",
      "source_url": "https://www.tiktok.com/@46_nhinguyen/video/7699467006587751688",
      "duration_seconds": 0.0,
      "file_size_mb": 9.26,
      "download_url": null
    },
    "execution_metrics": {
      "download_time_sec": 4.87,
      "keyframe_total_time_sec": 13.69,
      "total_time_sec": 60.62
    },
    "transcript": null,
    "keyframes": []
  },
  "error_message": null
}
```
