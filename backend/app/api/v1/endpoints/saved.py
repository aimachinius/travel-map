from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.saved import SavedPlaceResponse, SavedVideoResponse
from app.services.saved_service import SavedService

router = APIRouter(
    prefix="/saved",
    tags=["Saved Items"],
)


# --- 1. Saved Videos ---
@router.post(
    "/videos/{video_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Lưu video yêu thích (Idempotent: 201 nếu mới, 200 nếu đã lưu)",
)
def save_video(
    video_id: str,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        saved, is_new = SavedService.save_video(db, current_user.id, video_id)
        if not is_new:
            response.status_code = status.HTTP_200_OK
        return {
            "status": "success",
            "message": "Video đã được lưu vào danh sách yêu thích",
            "saved_id": str(saved.id),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bỏ lưu video yêu thích",
)
def unsave_video(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = SavedService.unsave_video(db, current_user.id, video_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video chưa được lưu",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/videos",
    response_model=list[SavedVideoResponse],
    summary="Danh sách video đã lưu kèm thông tin quán tương ứng",
)
def get_saved_videos(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = SavedService.get_saved_videos(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return items


# --- 2. Saved Places ---
@router.post(
    "/places/{place_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Lưu địa điểm yêu thích (Idempotent: 201 nếu mới, 200 nếu đã lưu)",
)
def save_place(
    place_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        saved, is_new = SavedService.save_place(db, current_user.id, place_id)
        if not is_new:
            response.status_code = status.HTTP_200_OK
        return {
            "status": "success",
            "message": "Địa điểm đã được lưu vào danh sách yêu thích",
            "saved_id": str(saved.id),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/places/{place_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bỏ lưu địa điểm yêu thích",
)
def unsave_place(
    place_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = SavedService.unsave_place(db, current_user.id, place_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Địa điểm chưa được lưu",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/places",
    response_model=list[SavedPlaceResponse],
    summary="Danh sách địa điểm đã lưu kèm số lượng video review",
)
def get_saved_places(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = SavedService.get_saved_places(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return items
