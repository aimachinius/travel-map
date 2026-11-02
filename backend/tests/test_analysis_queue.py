import pytest
from uuid import uuid4
from unittest.mock import patch

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
