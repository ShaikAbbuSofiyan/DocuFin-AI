from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.services.health_service import HealthService

router = APIRouter()


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness Probe",
    description="Returns 200 OK if the application server is up and responsive.",
    status_code=status.HTTP_200_OK,
)
async def liveness_probe() -> LivenessResponse:
    """Instantaneous process health check for container liveness probes."""
    service = HealthService()
    return service.get_liveness()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness Probe",
    description="Validates connectivity to required infrastructure (PostgreSQL, Redis). Returns 200 if fully operational, 503 if any dependency fails.",
)
async def readiness_probe(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ReadinessResponse:
    """Comprehensive readiness probe verifying PostgreSQL and Redis dependencies."""
    service = HealthService(session=db)
    is_ready, result = await service.get_readiness()
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        response.status_code = status.HTTP_200_OK
    return result
