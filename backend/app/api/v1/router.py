from fastapi import APIRouter

from app.api.v1.endpoints import audit, auth, chat, documents, health, organizations, reviews

api_v1_router = APIRouter()

# Register endpoint routers
api_v1_router.include_router(health.router, prefix="/health", tags=["Health & Diagnostics"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Sessions"])
api_v1_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations & RBAC"])
api_v1_router.include_router(documents.router, tags=["Documents & Isolation"])
api_v1_router.include_router(chat.router, tags=["Financial RAG Assistant"])
api_v1_router.include_router(reviews.router, tags=["Human Review Workflow"])
api_v1_router.include_router(audit.router, tags=["Audit Trails & Compliance"])

