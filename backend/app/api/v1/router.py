from fastapi import APIRouter
from app.api.v1.endpoints import auth, documents, health, organizations

api_v1_router = APIRouter()

# Register endpoint routers
api_v1_router.include_router(health.router, prefix="/health", tags=["Health & Diagnostics"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Sessions"])
api_v1_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations & RBAC"])
api_v1_router.include_router(documents.router, tags=["Documents & Isolation"])

