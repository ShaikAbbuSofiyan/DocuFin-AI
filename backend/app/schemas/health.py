from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    """Health status and latency metrics for an individual dependency."""

    status: str = Field(..., description="Component state: 'connected', 'degraded', or 'error'")
    latency_ms: Optional[float] = Field(None, description="Round-trip ping latency in milliseconds")
    details: Optional[str] = Field(None, description="Diagnostic detail or failure description")


class LivenessResponse(BaseModel):
    """Response payload for kubernetes/docker liveness probe (/health/live)."""

    status: str = Field(default="ok", description="Overall liveness status")
    app_name: str
    version: str
    environment: str
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Response payload for kubernetes/docker readiness probe (/health/ready)."""

    status: str = Field(..., description="Overall readiness: 'ready' or 'not_ready'")
    app_name: str
    version: str
    environment: str
    timestamp: datetime
    components: Dict[str, ComponentStatus]
