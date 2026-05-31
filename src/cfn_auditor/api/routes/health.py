"""Liveness endpoint. Unauthenticated, no DB."""

from fastapi import APIRouter

from cfn_auditor.api.schemas import HealthResponse

__all__ = ["router"]

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return ``{"status": "ok"}``. Always 200 when the process is up."""
    return HealthResponse(status="ok")
