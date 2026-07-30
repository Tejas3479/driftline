import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.auth.dependencies import get_current_user
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.digests.schemas import DigestResponseSchema, DigestGenerateRequestSchema
from src.digests.service import generate_weekly_digest, get_digest_by_id, list_digests

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["digests"])

@router.get("/digests/{id}")
async def get_digest_pdf_endpoint(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Serves/downloads the generated digest PDF file for the given digest ID.
    Returns HTTP 404 if digest record or physical file is missing.
    """
    digest = await get_digest_by_id(db, id)
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
async def list_digests_endpoint(
    workspace_id: Optional[int] = Query(None, description="Optional workspace ID filter"),
    metric_id: Optional[int] = Query(None, description="Optional metric ID filter"),
    db: AsyncSession = Depends(get_db)
):
    """Lists all generated digest records."""
    digests = await list_digests(db, workspace_id=workspace_id, metric_id=metric_id)
    return [DigestResponseSchema.model_validate(d) for d in digests]

@router.post("/digests/generate", response_model=DigestResponseSchema, status_code=status.HTTP_201_CREATED)
async def generate_digest_endpoint(
    payload: DigestGenerateRequestSchema,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers weekly digest generation for a metric and records/overwrites PDF file idempotently.
    """
    try:
        w_id = payload.workspace_id or 1
        digest = await generate_weekly_digest(db=db, workspace_id=w_id, metric_id=payload.metric_id)
        return DigestResponseSchema.model_validate(digest)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate digest PDF: {str(e)}")
