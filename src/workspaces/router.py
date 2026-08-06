import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, List

from src.db.session import get_db
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.db.models import Workspace
from src.auth.schemas import UserRead
from src.workspaces.schemas import WorkspaceUserCreate, UserUpdate
from src.auth.security import get_password_hash
from src.limiter import limiter
from src.audit import audit_log

from src.workspaces.service import (
    get_workspace as svc_get_workspace,
    list_workspace_users as svc_list_users,
    add_workspace_user as svc_add_user,
    update_user_role as svc_update_role,
    remove_user as svc_remove_user,
    UnauthorizedError
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.get("/me")
@limiter.limit("30/minute")
async def get_my_workspace(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    workspace = await svc_get_workspace(db, current_user.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

@router.get("/{workspace_id}/users", response_model=List[UserRead])
@limiter.limit("30/minute")
async def list_workspace_users(
    request: Request,
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    try:
        return await svc_list_users(db, workspace_id, current_user)
    except UnauthorizedError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/{workspace_id}/users", response_model=UserRead)
@limiter.limit("10/minute")
async def add_workspace_user(
    request: Request,
    workspace_id: int,
    user_in: WorkspaceUserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    try:
        user = await svc_add_user(db, workspace_id, user_in, current_user)
        audit_log("workspace.user_added", user_id=current_user.id, workspace_id=workspace_id,
                 resource_type="user", resource_id=user.id, details={"email": user_in.email, "role": user_in.role})
        return user
    except UnauthorizedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/users/{user_id}", response_model=UserRead)
@limiter.limit("10/minute")
async def update_user_role(
    request: Request,
    user_id: int,
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    try:
        user = await svc_update_role(db, user_id, update_data, current_user)
        audit_log("workspace.user_role_changed", user_id=current_user.id, workspace_id=current_user.workspace_id,
                 resource_type="user", resource_id=user_id, details=update_data.model_dump(exclude_unset=True))
        return user
    except UnauthorizedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        if str(e) == "User not found":
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/users/{user_id}")
@limiter.limit("10/minute")
async def remove_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    try:
        await svc_remove_user(db, user_id, current_user)
        audit_log("workspace.user_removed", user_id=current_user.id, workspace_id=current_user.workspace_id,
                 resource_type="user", resource_id=user_id)
        return {"status": "success"}
    except UnauthorizedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        if str(e) == "User not found":
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
