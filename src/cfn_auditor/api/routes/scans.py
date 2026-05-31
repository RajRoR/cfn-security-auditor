"""Scan endpoints: POST run, GET list, GET detail.

Persistence is delegated to ``cfn_auditor.engine.run_scan``; this module
does not reimplement Scan/Finding writes. Scoring is **computed on read**
at the boundary (per PR #7's recommendation) — never persisted on the Scan
row.

Error mapping (per the CLAUDE.md error-hygiene contract):
  * Malformed YAML / JSON                 → 400
  * Template too large                    → 413
  * Not a CloudFormation template (no
    Resources, etc.)                      → 400
  * Scan id not found                     → 404

No error response echoes template content. Messages name the template label
(when one was supplied) and the failure kind only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, desc, select

from cfn_auditor.api.dependencies import get_session, require_api_key
from cfn_auditor.api.schemas import (
    ScanCreateRequest,
    ScanDetailResponse,
    ScanSummaryResponse,
)
from cfn_auditor.engine import run_scan
from cfn_auditor.models import Scan
from cfn_auditor.parser import (
    MalformedTemplateError,
    NotACloudFormationTemplateError,
    TemplateTooLargeError,
)

__all__ = ["router"]

router = APIRouter(tags=["scans"], dependencies=[Depends(require_api_key)])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "/scans",
    response_model=ScanDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_scan(
    body: ScanCreateRequest,
    session: SessionDep,
) -> ScanDetailResponse:
    """Run a scan on the supplied template and return the persisted result."""
    try:
        scan = run_scan(body.template, body.name, session)
    except TemplateTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Template {body.name!r} exceeds the configured size limit.",
        ) from None
    except MalformedTemplateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template {body.name!r} is not valid YAML or JSON.",
        ) from None
    except NotACloudFormationTemplateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template {body.name!r} is not a CloudFormation template.",
        ) from None

    return ScanDetailResponse.from_scan(scan)


@router.get("/scans", response_model=list[ScanSummaryResponse])
def list_scans(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ScanSummaryResponse]:
    """List persisted scans newest-first; deterministic secondary sort by id desc."""
    statement = (
        select(Scan).order_by(desc(Scan.created_at), desc(Scan.id)).offset(offset).limit(limit)
    )
    scans = session.exec(statement).all()
    return [ScanSummaryResponse.from_scan(scan) for scan in scans]


@router.get("/scans/{scan_id}", response_model=ScanDetailResponse)
def get_scan(
    scan_id: int,
    session: SessionDep,
) -> ScanDetailResponse:
    """Return one scan with its findings and computed score."""
    scan = session.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found.",
        )
    return ScanDetailResponse.from_scan(scan)
