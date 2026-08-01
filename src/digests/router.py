import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from src.auth.dependencies import get_current_user
from src.ingestion.service import verify_metric_access
from src.auth.models import User
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.digests.schemas import DigestResponseSchema, DigestGenerateRequestSchema
from src.digests.service import generate_weekly_digest, get_digest_by_id, list_digests
from src.limiter import limiter

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["digests"])

@router.get("/digests/{id}")
@limiter.limit("30/minute")
async def get_digest_pdf_endpoint(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Serves/downloads the generated digest PDF file for the given digest ID.
    Returns HTTP 404 if digest record or physical file is missing.
    """
    digest = await get_digest_by_id(db, id, current_user.workspace_id)
    if not digest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Digest with id {id} not found.")

    if not os.path.exists(digest.pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"PDF file for digest #{id} is missing from disk.")

    file_basename = os.path.basename(digest.pdf_path)
    return FileResponse(
        path=digest.pdf_path,
        media_type="application/pdf",
        filename=file_basename
    )

@router.get("/digests", response_model=List[DigestResponseSchema])
@limiter.limit("30/minute")
async def list_digests_endpoint(
    request: Request,
    metric_id: Optional[int] = Query(None, description="Optional metric ID filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all generated digest records."""
    digests = await list_digests(db, workspace_id=current_user.workspace_id, metric_id=metric_id)
    return [DigestResponseSchema.model_validate(d) for d in digests]

@router.post("/digests/generate", response_model=DigestResponseSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def generate_digest_endpoint(
    request: Request,
    payload: DigestGenerateRequestSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually triggers weekly digest generation for a metric and records/overwrites PDF file idempotently.
    """
    await verify_metric_access(payload.metric_id, db, current_user.workspace_id)
    try:
        digest = await generate_weekly_digest(db=db, workspace_id=current_user.workspace_id, metric_id=payload.metric_id)
        return DigestResponseSchema.model_validate(digest)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate digest PDF: {str(e)}")
