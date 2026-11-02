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
  "status": "SUCCESS",
  "message": "AI extracted restaurant information successfully",
  "data": {
    "video": {
      "title": "Review ẩm thực: Bánh Xèo Bà Dưỡng cực ngon tại Đà Nẵng",
      "duration_seconds": 45.2,
      "file_size_mb": 21.4
    },
    "transcript": {
      "text": "Quán bánh xèo Bà Dưỡng nằm trong kiệt 280 Hoàng Diệu...",
      "language": "vi"
    },
    "restaurant": {
      "name": "Bánh Xèo Bà Dưỡng",
      "address": "K280/23 Hoàng Diệu, Bình Hiên, Hải Châu, Đà Nẵng",
      "category": "Quán ăn",
      "confidence_status": "HIGH",
      "evidence_sources": ["OCR_SIGNBOARD", "TRANSCRIPT", "CAPTION"]
    }
  }
}
```
