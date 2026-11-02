from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.place import NearbyVideoItem, PlaceResponse, PlaceVideoMatchItem
from app.services.place_service import PlaceService

router = APIRouter(
    prefix="/places",
    tags=["Places"],
)


@router.get(
    "/nearby-videos",
    response_model=list[NearbyVideoItem],
    summary="Tìm kiếm video trong bán kính xung quanh tọa độ",
)
def get_nearby_videos(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Vĩ độ"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Kinh độ"),
    radius_m: float = Query(default=2000.0, ge=10.0, le=50000.0, description="Bán kính tính bằng mét"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    current_user_id = current_user.id if current_user else None
    results = PlaceService.get_nearby_videos(
        db=db,
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        limit=limit,
        offset=offset,
        current_user_id=current_user_id,
    )
    return results


@router.get(
    "/search",
    response_model=list[PlaceResponse],
    summary="Tìm kiếm địa điểm theo từ khóa hoặc thể loại",
)
def search_places(
    q: str | None = Query(default=None, max_length=100, description="Từ khóa tên quán hoặc địa chỉ"),
    category: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    places = PlaceService.search_places(
        db=db,
        query_str=q,
        category=category,
        limit=limit,
        offset=offset,
    )
    return places


@router.get(
    "/{place_id}",
    response_model=PlaceResponse,
    summary="Xem chi tiết một địa điểm ăn uống",
)
def get_place_detail(
    place_id: UUID,
    db: Session = Depends(get_db),
):
    place = PlaceService.get_place_detail(db, place_id)
    if place is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy địa điểm",
        )
    return place


@router.get(
    "/{place_id}/videos",
    response_model=list[PlaceVideoMatchItem],
    summary="Lấy toàn bộ video review của một quán ăn (ưu tiên confidence HIGH)",
)
def get_place_videos(
    place_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    place = PlaceService.get_place_detail(db, place_id)
    if place is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy địa điểm",
        )

    results = PlaceService.get_place_videos(
        db=db,
        place_id=place_id,
        limit=limit,
        offset=offset,
    )
    return results
