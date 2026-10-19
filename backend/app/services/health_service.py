import time
from datetime import datetime, timezone
from typing import Dict, Tuple
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.logging import logger
from app.schemas.health import ComponentStatus, LivenessResponse, ReadinessResponse


class HealthService:
    """Service providing dependency health checks and system operational metrics."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self.settings = get_settings()

    def get_liveness(self) -> LivenessResponse:
        """Returns instantaneous process liveness."""
        return LivenessResponse(
            status="ok",
            app_name=self.settings.app_name,
            version=self.settings.app_version,
            environment=self.settings.environment,
            timestamp=datetime.now(timezone.utc),
        )

    async def check_database(self) -> ComponentStatus:
        """Verifies PostgreSQL connectivity by executing a lightweight SELECT 1 query."""
        if not self.session:
            return ComponentStatus(
                status="error",
                details="No database session provided.",
            )

        start = time.perf_counter()
        try:
            result = await self.session.execute(text("SELECT 1"))
            val = result.scalar()
            latency = round((time.perf_counter() - start) * 1000, 2)
            if val == 1:
                return ComponentStatus(status="connected", latency_ms=latency)
            return ComponentStatus(
                status="error",
                latency_ms=latency,
                details=f"Unexpected query response: {val}",
            )
        except Exception as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            logger.warning(f"Database health check failed: {exc}")
            return ComponentStatus(
                status="error",
                latency_ms=latency,
                details=str(exc),
            )

    async def check_redis(self) -> ComponentStatus:
        """Verifies Redis cache connectivity by sending a PING command."""
        start = time.perf_counter()
        client = None
        try:
            client = aioredis.from_url(
                self.settings.redis_connection_url,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
                decode_responses=True,
            )
            pong = await client.ping()
            latency = round((time.perf_counter() - start) * 1000, 2)
            if pong:
                return ComponentStatus(status="connected", latency_ms=latency)
            return ComponentStatus(
                status="error",
                latency_ms=latency,
                details="Redis ping returned non-truthy value",
            )
        except Exception as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            logger.warning(f"Redis health check failed: {exc}")
            return ComponentStatus(
                status="error",
                latency_ms=latency,
                details=str(exc),
            )
        finally:
            if client:
                try:
                    await client.aclose()
                except Exception:
                    pass

    async def get_readiness(self) -> Tuple[bool, ReadinessResponse]:
        """Evaluates readiness across all critical infrastructure dependencies."""
        db_status = await self.check_database()
        redis_status = await self.check_redis()

        components: Dict[str, ComponentStatus] = {
            "database": db_status,
            "redis": redis_status,
        }

        # Ready only if both database and redis are connected
        is_ready = (db_status.status == "connected" and redis_status.status == "connected")

        response = ReadinessResponse(
            status="ready" if is_ready else "not_ready",
            app_name=self.settings.app_name,
            version=self.settings.app_version,
            environment=self.settings.environment,
            timestamp=datetime.now(timezone.utc),
            components=components,
        )
        return is_ready, response
