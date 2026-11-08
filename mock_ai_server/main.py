from fastapi import FastAPI, Request

app = FastAPI(title="Mock AI Server")


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-ai-server"}


@app.post("/api/v1/extract")
async def extract_location(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}

    url = body.get("url", "")
    return {
        "status": "SUCCESS",
        "success": True,
        "video_url": url,
        "data": {
            "video": {
                "title": "Review Quán Bánh Mì Huỳnh Hoa Sài Gòn Nức Tiếng",
                "duration_seconds": 45,
                "file_size_mb": 8.5,
            },
            "transcript": {
                "text": "Hôm nay tụi mình ghé quán Bánh Mì Huỳnh Hoa tại 26 Lê Thị Riêng Quận 1 để thưởng thức ổ bánh mì pate siêu nhiều thịt chả."
            },
            "restaurant": {
                "name": "Bánh Mì Huỳnh Hoa",
                "address": "26 Lê Thị Riêng, Phường Bến Thành, Quận 1, Thành phố Hồ Chí Minh",
                "category": "Ăn Vặt & Đường Phố",
                "confidence_status": "HIGH",
                "evidence_sources": ["audio_transcript", "ocr_text"],
                "evidence": "Bảng hiệu và âm thanh nhắc đến Bánh Mì Huỳnh Hoa 26 Lê Thị Riêng",
            },
            "food_items": ["Bánh mì pate chả", "Bơ tươi"],
        },
        "place": {
            "name": "Bánh Mì Huỳnh Hoa",
            "address": "26 Lê Thị Riêng, Phường Bến Thành, Quận 1, Thành phố Hồ Chí Minh",
            "latitude": 10.7719,
            "longitude": 106.6925,
            "category": "Ăn Vặt & Đường Phố",
            "confidence": 0.95,
        },
        "message": "Trích xuất thông tin thành công từ video",
    }
