import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.place import NearbyVideoItem, PlaceResponse, PlaceVideoMatchItem
from app.services.place_service import PlaceService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/places",
    tags=["Places"],
)


async def _trigger_discovery_task(lat: float, lon: float, radius_m: float) -> None:
    """Kích hoạt ngầm tiến trình Discovery cào video theo vị trí thông qua BackgroundTasks."""
    logger.info(f">>> [TRIGGER DISCOVERY] Nhận yêu cầu chạy Discovery nền cho ({lat}, {lon}), bán kính {radius_m}m...")
    from app.db.session import SessionLocal
    from app.services.analysis_service import enqueue_analysis
    from app.services.discovery_service import DiscoveryService

    with SessionLocal() as bg_db:
        try:
            await DiscoveryService.discover_location(
                db=bg_db,
                lat=lat,
                lon=lon,
                radius_m=radius_m,
                enqueue_callback=enqueue_analysis,
            )
        except Exception as e:
            logger.warning(f"Background discovery task encountered error: {e}", exc_info=True)


@router.get(
    "/nearby-videos",
    response_model=list[NearbyVideoItem],
    summary="Tìm kiếm video trong bán kính xung quanh tọa độ",
)
async def get_nearby_videos(
    background_tasks: BackgroundTasks,
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

    # Kích hoạt ngầm DiscoveryService qua FastAPI BackgroundTasks (tự động kiểm tra chống quét lặp 1km/24h)
    background_tasks.add_task(_trigger_discovery_task, lat, lon, radius_m)

    return results


@router.get(
    "",
    response_model=list[PlaceResponse],
    summary="Lấy danh sách địa điểm ăn uống",
)
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
