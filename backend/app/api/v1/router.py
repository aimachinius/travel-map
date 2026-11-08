from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.places import router as places_router
from app.api.v1.endpoints.saved import router as saved_router
from app.api.v1.endpoints.videos import router as videos_router
from app.api.v1.endpoints.ws import router as ws_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(videos_router)
api_router.include_router(places_router)
api_router.include_router(saved_router)
api_router.include_router(ws_router)