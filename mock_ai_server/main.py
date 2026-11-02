"""
Mock External AI Server cho Food Spot
Mô phỏng endpoint POST /api/v1/extract để phục vụ kiểm thử phân tích video
trả về địa điểm ẩm thực ngẫu nhiên tại khu vực Đà Nẵng.
"""

import asyncio
import logging
import random
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mock_ai_server")

app = FastAPI(
    title="Food Spot Mock AI Server",
    description="Server mô phỏng pipeline AI trích xuất địa điểm quán ăn từ video review",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Danh sách các địa điểm ẩm thực nổi tiếng tại Đà Nẵng với địa chỉ chính xác
DANANG_FOOD_SPOTS = [
    {
        "name": "Bún Chả Cá Bà Lữ",
        "address": "319 Hùng Vương, Vĩnh Trung, Thanh Khê, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Hôm nay mình ghé bún chả cá Bà Lữ tại 319 Hùng Vương Đà Nẵng. Nước dùng ngọt thanh đậm đà từ xương cá, chả cá chiên và chả cá hấp dai ngon chuẩn vị miền Trung.",
    },
    {
        "name": "Mì Quảng Bà Mua",
        "address": "19 Trần Bình Trọng, Phước Ninh, Hải Châu, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Đi Đà Nẵng không thể bỏ qua Mì Quảng Bà Mua ở 19 Trần Bình Trọng. Sợi mì dai vàng, tôm thịt đậm vị, bánh tráng giòn rụm và rau sống tươi ngon hết sẩy.",
    },
    {
        "name": "Bánh Xèo Bà Dưỡng",
        "address": "K280/23 Hoàng Diệu, Bình Hiên, Hải Châu, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Quán bánh xèo Bà Dưỡng nằm trong kiệt 280 Hoàng Diệu cực kỳ đông khách. Vỏ bánh xèo giòn rụm, nước chấm tương đậu phộng béo bùi độc quyền siêu cuốn.",
    },
    {
        "name": "Cơm Gà A Hải",
        "address": "100 Thái Phiên, Phước Ninh, Hải Châu, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Cơm gà xối mỡ A Hải tại 100 Thái Phiên. Da gà giòn rụm, thịt bên trong mềm mọng nước, hạt cơm vàng ươm dẻo thơm ăn kèm dưa chua chấm sốt rất ngon.",
    },
    {
        "name": "Bún Mắm Nêm Bà Thuyên",
        "address": "424/3 Lê Duẩn, Chính Gián, Thanh Khê, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Đến Đà Nẵng phải thử bún mắm nêm Bà Thuyên ở kiệt 424 Lê Duẩn. Thịt heo quay giòn rụm, nem chả thơm phức hòa quyện cùng mắm nêm đậm đà thơm ngậy.",
    },
    {
        "name": "Bánh Tráng Cuốn Thịt Heo Trần",
        "address": "04 Lê Duẩn, Hải Châu 1, Hải Châu, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Bánh tráng cuốn thịt heo Đại Lộc quán Trần số 4 Lê Duẩn Đà Nẵng. Thịt hai đầu da luộc cắt mỏng cuộn bánh tráng, rau rừng chấm mắm nêm tuyệt hảo.",
    },
    {
        "name": "Chè Sầu Liên",
        "address": "189 Hoàng Diệu, Nam Dương, Hải Châu, Đà Nẵng",
        "category": "Cà phê",
        "transcript": "Món tráng miệng nổi tiếng nhất Đà Nẵng - Chè sầu Bà Liên 189 Hoàng Diệu. Sầu riêng tươi béo ngậy kết hợp nước cốt dừa, thạch và trân châu ăn cực đã mát lạnh.",
    },
    {
        "name": "Hải Sản Năm Đảnh",
        "address": "K139/H59/38 Trần Quang Khải, Thọ Quang, Sơn Trà, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Hải sản Năm Đảnh nằm sâu trong hẻm Trần Quang Khải quận Sơn Trà nhưng lúc nào cũng kín bàn. Đầy đủ các món ốc hương xào bơ tỏi, mực hấp, ghẹ rang me đồng giá tươi sống.",
    },
    {
        "name": "Bánh Canh Ruộng Cầu Thuận Phước",
        "address": "20 Hà Thị Thân, An Hải Tây, Sơn Trà, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Bánh canh ruộng giá rẻ nức tiếng gần cầu Rồng. Nước dùng nấu từ cá ngừ đậm vị cay nồng, sợi bột lọc dẻo dai ăn kèm quẩy giòn tan.",
    },
    {
        "name": "Gỏi Cá Nam Ô Bà Hiền",
        "address": "1315 Nguyễn Lương Bằng, Hòa Hiệp Nam, Liên Chiểu, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Gỏi cá Nam Ô Bà Hiền trên đường Nguyễn Lương Bằng. Cá trích tươi rói cuốn lá đinh lăng chấm nước sốt mắm mè đậu phộng trứ danh vùng biển Nam Ô.",
    },
    {
        "name": "Cà Phê Trứng 43 Factory",
        "address": "422 Ngô Quyền, An Hải Bắc, Sơn Trà, Đà Nẵng",
        "category": "Cà phê",
        "transcript": "Quán cà phê không gian mở hiện đại tại đường Ngô Quyền Sơn Trà. Phục vụ cà phê specialty cùng kem trứng béo mịn thích hợp làm việc và ngắm cảnh.",
    },
    {
        "name": "Bê Thui Cầu Mống Mười Hiển",
        "address": "138 Nguyễn Tri Phương, Chính Gián, Thanh Khê, Đà Nẵng",
        "category": "Quán ăn",
        "transcript": "Bê thui Cầu Mống Mười Hiển đường Nguyễn Tri Phương. Thịt bê mềm ngọt với phần da giòn sần sật cuốn rau sống chấm nước mắm cá cơm chuẩn gốc Quảng Nam.",
    },
]


class ExtractRequest(BaseModel):
    url: str = Field(..., description="Link video TikTok hoặc YouTube Shorts cần phân tích")
    mock_index: int | None = Field(None, description="Tùy chọn chỉ định quán ăn theo index (0-11) để test cố định")
    simulated_delay_seconds: float | None = Field(1.5, description="Thời gian giả lập AI xử lý video")


@app.get("/")
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Food Spot Mock AI Extraction Server",
        "total_sample_places": len(DANANG_FOOD_SPOTS),
        "endpoint": "POST /api/v1/extract",
    }


@app.post("/api/v1/extract")
async def extract_restaurant_info(req: ExtractRequest) -> dict[str, Any]:
    """
    Mô phỏng pipeline trích xuất OCR, ASR, NER từ video review.
    Đầu ra tuân thủ chính xác khế ước mong đợi bởi Backend AnalysisService.
    """
    logger.info("Nhận yêu cầu phân tích video URL: %s", req.url)

    # Giả lập thời gian trích xuất frame và chạy model AI (để thấy trạng thái PROCESSING trên WebSocket)
    delay = req.simulated_delay_seconds if req.simulated_delay_seconds is not None else 1.5
    if delay > 0:
        await asyncio.sleep(delay)

    # Chọn địa điểm Đà Nẵng (ngẫu nhiên hoặc theo chỉ số test)
    if req.mock_index is not None and 0 <= req.mock_index < len(DANANG_FOOD_SPOTS):
        spot = DANANG_FOOD_SPOTS[req.mock_index]
    else:
        spot = random.choice(DANANG_FOOD_SPOTS)

    # Tạo các thông số video ngẫu nhiên thực tế
    duration = round(random.uniform(25.0, 85.0), 1)
    file_size = round(random.uniform(12.0, 48.0), 2)

    response_payload = {
        "status": "SUCCESS",
        "message": "AI extracted restaurant information successfully",
        "data": {
            "video": {
                "title": f"Review ẩm thực: {spot['name']} cực ngon tại Đà Nẵng",
                "duration_seconds": duration,
                "file_size_mb": file_size,
            },
            "transcript": {
                "text": spot["transcript"],
                "language": "vi",
            },
            "restaurant": {
                "name": spot["name"],
                "address": spot["address"],
                "category": spot["category"],
                "confidence_status": "HIGH",
                "evidence_sources": ["OCR_SIGNBOARD", "TRANSCRIPT", "CAPTION"],
            },
            "keyframes": [
                {
                    "timestamp": 2.5,
                    "description": f"Biển hiệu {spot['name']}",
                    "confidence": 0.95,
                },
                {
                    "timestamp": round(duration * 0.4, 1),
                    "description": "Không gian quán và chế biến món ăn",
                    "confidence": 0.88,
                },
                {
                    "timestamp": round(duration * 0.8, 1),
                    "description": "Món ăn hoàn chỉnh dọn lên bàn",
                    "confidence": 0.92,
                },
            ],
            "frames_ocr_details": [
                {
                    "text": spot["name"],
                    "confidence": 0.96,
                    "box": [120, 85, 340, 150],
                },
                {
                    "text": spot["address"],
                    "confidence": 0.91,
                    "box": [115, 160, 480, 210],
                },
            ],
            "execution_metrics": {
                "total_frames_sampled": 140,
                "ocr_latency_ms": 380,
                "asr_latency_ms": 620,
                "total_duration_ms": int(delay * 1000),
            },
        },
    }

    logger.info("Trích xuất hoàn tất! Trả về quán: %s - %s", spot["name"], spot["address"])
    return response_payload


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
