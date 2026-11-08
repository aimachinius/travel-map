import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.analysis_service import (
    enqueue_analysis,
    dequeue_next_analysis,
    _in_memory_high_queue,
    _in_memory_low_queue,
)


@pytest.mark.asyncio
async def test_strict_priority_queue_polling():
    # Xóa hàng đợi fallback
    while not _in_memory_high_queue.empty():
        _in_memory_high_queue.get_nowait()
    while not _in_memory_low_queue.empty():
        _in_memory_low_queue.get_nowait()

    low_task1 = str(uuid4())
    low_task2 = str(uuid4())
    high_task = str(uuid4())

    # Đẩy 2 task low priority trước (giả lập System Discovery)
    with patch("app.services.analysis_service.get_redis_client", return_value=None):
        await enqueue_analysis(low_task1, priority=2)
        await enqueue_analysis(low_task2, priority=2)

        # Sau đó user submit đẩy 1 task high priority
        await enqueue_analysis(high_task, priority=1)

        # Lần pop đầu tiên BẮT BUỘC phải là high_task
        task, priority = await dequeue_next_analysis()
        assert task == high_task
        assert priority == 1

        # Lần pop tiếp theo là low_task1
        task, priority = await dequeue_next_analysis()
        assert task == low_task1
        assert priority == 2

        # Lần pop thứ 3 là low_task2
        task, priority = await dequeue_next_analysis()
        assert task == low_task2
        assert priority == 2

        # Hàng đợi trống
        task, priority = await dequeue_next_analysis()
        assert task is None
        assert priority == 0


@pytest.mark.asyncio
async def test_process_analysis_run_handles_null_transcript_and_vietnamese_confidence():
    from app.models.analysis_run import AnalysisRun
    from app.models.video import Video
    from app.models.place import Place
    from app.models.video_place_match import VideoPlaceMatch
    from app.services.analysis_service import process_analysis_run

    run_id = uuid4()
    vid_id = uuid4()
    u_id = uuid4()

    analysis = AnalysisRun(
        id=run_id,
        video_id=vid_id,
        submitted_url="https://www.tiktok.com/@46_nhinguyen/video/7699467006587751688",
        status="PENDING",
        trigger_source="USER_SUBMIT",
        user_id=u_id,
    )
    video = Video(
        id=vid_id,
        platform="tiktok",
        platform_video_id="7699467006587751688",
        video_url=analysis.submitted_url,
    )

    db = MagicMock()
    # Mock db.get: trả về analysis hoặc video tương ứng
    def mock_get(model, pk):
        if model == AnalysisRun and pk == run_id:
            return analysis
        if model == Video and pk == vid_id:
            return video
        return None

    db.get.side_effect = mock_get
    db.scalar.return_value = None  # Không có place hoặc match tồn tại trước

    # Payload mô phỏng chính xác mẫu response AI server
    ai_payload = {
        "success": True,
        "status": "SUCCESS",
        "data": {
            "restaurant": {
                "name": "HongKong Style",
                "address": "181 Nguyễn Văn Thoại, Đà Nẵng",
                "confidence_status": "Cao",
                "evidence": {
                    "name_source": "Frame 3, Frame 5 (OCR)",
                    "address_source": "Frame 1, Frame 4 (OCR)",
                },
                "evidence_sources": [
                    "Frame 3, Frame 5 (OCR)",
                    "Frame 1, Frame 4 (OCR)",
                ],
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
                    "ocr_other": None,
                }
            ],
            "video": {
                "video_id": "7699467006587751688",
                "platform": "tiktok",
                "source_url": "https://www.tiktok.com/@46_nhinguyen/video/7699467006587751688",
                "duration_seconds": 0.0,
                "file_size_mb": 9.26,
                "download_url": None,
            },
            "execution_metrics": {
                "total_time_sec": 60.62,
            },
            "transcript": None,
            "keyframes": [],
        },
        "error_message": None,
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ai_payload

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch(
        "app.services.geocoding_service.ArcGISGeocoder.geocode_address",
        new=AsyncMock(return_value=(16.05, 108.24, "181 Nguyễn Văn Thoại, Đà Nẵng")),
    ), patch(
        "app.services.analysis_service.websocket_manager.broadcast_analysis_update",
        new=AsyncMock(),
    ):
        result = await process_analysis_run(db, run_id, http_client=mock_client)

        assert result.status == "COMPLETED"
        assert result.error_message is None
        assert video.transcript is None
        assert video.transcript_text is None
        assert result.keyframes_data == []
        assert len(result.ocr_data) == 1

        # Kiểm tra VideoPlaceMatch được tạo với confidence_status đã chuẩn hóa thành HIGH
        added_objs = [call[0][0] for call in db.add.call_args_list]
        matches = [obj for obj in added_objs if isinstance(obj, VideoPlaceMatch)]
        assert len(matches) == 1
        assert matches[0].confidence_status == "HIGH"
        assert matches[0].evidence == ai_payload["data"]["restaurant"]["evidence"]

