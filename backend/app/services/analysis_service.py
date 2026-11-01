
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun


def start_analysis(
    db: Session,
    analysis_run_id: UUID,
) -> AnalysisRun:
    analysis = db.get(AnalysisRun, analysis_run_id)

    if analysis is None:
        raise ValueError("Không tìm thấy yêu cầu phân tích")

    if analysis.status != "PENDING":
        raise ValueError("Chỉ có thể bắt đầu yêu cầu đang PENDING")

    analysis.status = "PROCESSING"
    analysis.started_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(analysis)

    return analysis


def complete_analysis(
    db: Session,
    analysis_run_id: UUID,
    result_place_id: UUID | None = None,
) -> AnalysisRun:
    analysis = db.get(AnalysisRun, analysis_run_id)

    if analysis is None:
        raise ValueError("Không tìm thấy yêu cầu phân tích")

    if analysis.status != "PROCESSING":
        raise ValueError("Yêu cầu phải ở trạng thái PROCESSING")

    analysis.status = "COMPLETED"
    analysis.result_place_id = result_place_id
    analysis.error_message = None
    analysis.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(analysis)

    return analysis


def fail_analysis(
    db: Session,
    analysis_run_id: UUID,
    error_message: str,
) -> AnalysisRun:
    analysis = db.get(AnalysisRun, analysis_run_id)

    if analysis is None:
        raise ValueError("Không tìm thấy yêu cầu phân tích")

    if analysis.status not in ("PENDING", "PROCESSING"):
        raise ValueError("Không thể đánh dấu thất bại cho yêu cầu này")

    analysis.status = "FAILED"
    analysis.error_message = error_message
    analysis.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(analysis)

    return analysis
