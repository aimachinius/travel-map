# Hướng Dẫn Sử Dụng Module `src/` (AI Server v3.0 - Pure Vision & GPU Acceleration)

Hệ thống trích xuất thông tin quán ăn (tên quán, địa chỉ) tốc độ cao trên video ngắn (TikTok, YouTube Shorts), tối ưu hóa đặc biệt cho **Google Colab (GPU T4/L4/A100)**:
1. **Lấy mẫu 1 lượt nhanh (`FastSinglePassSampler`)**: Đọc tuần tự video với `cap.grab()` + lọc biến thiên ảnh thu nhỏ $64 \times 64$, giải mã toàn bộ video trong $< 1.2$ giây mà không cần `PySceneDetect`.
2. **Phát hiện vùng chữ trên GPU (`GPUDBNetDetector`)**: Tận dụng `CUDAExecutionProvider` + `max_side=640` + mini-batch, phát hiện hộp chữ chỉ trong $0.3\text{s} - 0.6\text{s}$.
3. **Trích xuất Pure Vision 3 bước (`Vintern1BExtractor`)**: Loại bỏ hoàn toàn Speech-to-Text (PhoWhisper), tiết kiệm 3.5 GB VRAM và 30s-60s thời gian xử lý, cơ chế Majority Voting & Fast-Path bypass khi các frame đồng thuận.

---

## 1. Cài Đặt Thư Viện Trên Google Colab

Trên Google Colab (đảm bảo Runtime Type là **T4 GPU** hoặc cao hơn):

```bash
# 1. Di chuyển vào thư mục dự án
%cd /content/drive/MyDrive/colab/pbl/main

# 2. Cài đặt các gói phụ thuộc (v3.0 Pure Vision với onnxruntime-gpu)
!pip install -q -r src/requirements.txt
```

---

## 2. Khởi Chạy AI Server Trên Google Colab

Để khởi chạy server trên Colab và tự động tạo đường link công khai HTTPS qua **Cloudflare Tunnel**:

```bash
# Trong Colab notebook cell:
!python src/run_server.py --port 8000 --tunnel cloudflare
```

*Đầu ra sẽ cung cấp Public URL:*
```text
============================================================
🎉 [CẦU NỐI CLOUDFLARE TUNNEL THÀNH CÔNG!]
🌐 Public URL (HTTPS): https://<random-subdomain>.trycloudflare.com
🏠 Local URL         : http://127.0.0.1:8000
============================================================
```

- **Swagger UI (Docs)**: `https://<subdomain>.trycloudflare.com/docs`
- **Health Check**: `https://<subdomain>.trycloudflare.com/api/v1/health`
- **Extract API**: `POST https://<subdomain>.trycloudflare.com/api/v1/extract`

---

## 3. Cấu Trúc Thư Mục Hệ Thống

```text
src/
├── config/                 # Cấu hình tập trung (paths, GPU thresholds, vlm settings)
│   └── settings.py
├── utils/                  # Tiện ích I/O an toàn Unicode/Google Drive ('マイドライブ') & Logger
│   ├── io_utils.py
│   └── logger.py
├── detectors/              # Tiền xử lý thị giác (FastSinglePassSampler + GPU DBNet ONNX)
│   ├── scene_detector.py   # FastSinglePassSampler (cap.grab + 64x64 diff filter)
│   ├── text_detector.py    # GPUDBNetDetector (CUDAExecutionProvider + max_side=640)
│   └── frame_selector.py   # TextKeyframeSelector (Stratified Top-K + NMS)
├── vlm/                    # Mô hình thị giác ngôn ngữ Vintern-1B Pure Vision
│   ├── preprocessor.py     # Dynamic resolution (448x448 patches)
│   ├── prompt_builder.py   # Prompt 3 bước OCR + Conclude (không phụ thuộc STT)
│   └── vintern_extractor.py# Wrapper Vintern-1B Pure Vision (Majority Voting + Fast-Path)
├── server/                 # REST API FastAPI độc lập
│   ├── app.py              # Ứng dụng chính & Lifespan
│   ├── dependencies.py     # GPU Mutex Lock & Singleton Management
│   ├── routes/             # Health, Extract, Jobs endpoints
│   ├── schemas/            # Pydantic Request/Response v3.0 schemas
│   └── services/           # ServerExtractionPipeline, VideoDownloader, Storage, Tunnel
├── batch/                  # Xử lý hàng loạt từ CSV kèm checkpoint
│   └── batch_processor.py
├── tests/                  # Bộ kiểm thử 7 module độc lập & CLI runner
│   ├── run_tests.py
│   └── TESTING.md
└── run_server.py           # CLI khởi chạy chính thức cho Server
```

---

## 4. Chạy Kiểm Thử Độc Lập (Test Suite)

Để kiểm tra toàn bộ hoặc từng module trên môi trường Colab:

```bash
# Chạy toàn bộ 7 module kiểm thử:
!python src/tests/run_tests.py --module all

# Hoặc kiểm thử riêng từng module:
!python src/tests/run_tests.py --module vision     # FastSinglePassSampler & GPU DBNet
!python src/tests/run_tests.py --module vlm        # Pure Vision 3 bước & Fast-Path
!python src/tests/run_tests.py --module pipeline   # Luồng trích xuất End-to-End
!python src/tests/run_tests.py --module api        # REST API FastAPI
```
Chi tiết về các kịch bản kiểm thử: Xem [src/tests/TESTING.md](file:///g:/マイドライブ/colab/pbl/main/src/tests/TESTING.md).

