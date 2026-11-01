
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.place import Place
from app.models.saved_place import SavedPlace
from app.models.user import User
from app.schemas.place import PlaceResponse


router = APIRouter(
    prefix="/places",
    tags=["Places"],
)


# 1. Get and search places
@router.get(
    "",
    response_model=list[PlaceResponse],
)
def get_places(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Place).where(Place.is_active.is_(True))

    if q and q.strip():
        keyword = func.lower(func.unaccent(q.strip()))

        normalized_name = func.lower(func.unaccent(Place.name))
        normalized_address = func.lower(func.unaccent(Place.address))
        normalized_description = func.lower(func.unaccent(Place.description))
        normalized_category = func.lower(func.unaccent(Place.category))

        query = query.where(
            or_(
                normalized_name.ilike(func.concat("%", keyword, "%")),
                normalized_address.ilike(func.concat("%", keyword, "%")),
                normalized_description.ilike(func.concat("%", keyword, "%")),
                normalized_category.ilike(func.concat("%", keyword, "%")),
                func.similarity(normalized_name, keyword) >= 0.3,
                func.similarity(normalized_address, keyword) >= 0.3,
            )
        )

    if category and category.strip():
        query = query.where(
            func.lower(func.unaccent(Place.category))
            == func.lower(func.unaccent(category.strip()))
        )

    places = db.scalars(
        query
        .order_by(Place.name.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    return places


# 2. Get saved places
# Keep this route before /{place_id}
@router.get(
    "/saved",
    response_model=list[PlaceResponse],
)
def get_saved_places(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    places = db.scalars(
        select(Place)
        .join(
            SavedPlace,
            SavedPlace.place_id == Place.id,
        )
        .where(
            SavedPlace.user_id == current_user.id,
            Place.is_active.is_(True),
        )
        .order_by(SavedPlace.created_at.desc())
    ).all()

    return places


# 3. Get place detail
@router.get(
    "/{place_id}",
    response_model=PlaceResponse,
)
def get_place_detail(
    place_id: UUID,
    db: Session = Depends(get_db),
):
    place = db.get(Place, place_id)

    if place is None or not place.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place not found",
        )

    return place


# 4. Save a place
@router.post(
    "/{place_id}/save",
    response_model=PlaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_place(
    place_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    place = db.get(Place, place_id)

    if place is None or not place.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place not found",
        )

    existing = db.scalar(
        select(SavedPlace).where(
            SavedPlace.user_id == current_user.id,
            SavedPlace.place_id == place_id,
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Place has already been saved",
        )

    saved_place = SavedPlace(
        user_id=current_user.id,
        place_id=place_id,
    )

    db.add(saved_place)
    db.commit()

    return place


# 5. Unsave a place
@router.delete(
    "/{place_id}/save",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unsave_place(
    place_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved_place = db.scalar(
        select(SavedPlace).where(
            SavedPlace.user_id == current_user.id,
            SavedPlace.place_id == place_id,
        )
    )

    if saved_place is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place has not been saved",
        )

    db.delete(saved_place)
    db.commit()

    return None
