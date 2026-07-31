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

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.get("/me")
@limiter.limit("30/minute")
async def get_my_workspace(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    res = await db.execute(select(Workspace).where(Workspace.id == current_user.workspace_id))
    workspace = res.scalar_one_or_none()
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
    if current_user.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this workspace")
        
    res = await db.execute(select(User).where(User.workspace_id == workspace_id))
    return res.scalars().all()

@router.post("/{workspace_id}/users", response_model=UserRead)
@limiter.limit("10/minute")
async def add_workspace_user(
    request: Request,
    workspace_id: int,
    user_in: WorkspaceUserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    if current_user.workspace_id != workspace_id or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to add users to this workspace")
        
    # Check if user exists
    res = await db.execute(select(User).where(User.email == user_in.email))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
        
    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        workspace_id=workspace_id,
        role=user_in.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.patch("/users/{user_id}", response_model=UserRead)
@limiter.limit("10/minute")
async def update_user_role(
    request: Request,
    user_id: int,
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Get target user
    res = await db.execute(select(User).where(User.id == user_id))
    target_user = res.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if current_user.workspace_id != target_user.workspace_id or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to modify this user")
        
    if update_data.role not in ["admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    target_user.role = update_data.role
    await db.commit()
    await db.refresh(target_user)
    return target_user

@router.delete("/users/{user_id}")
@limiter.limit("10/minute")
async def remove_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Get target user
    res = await db.execute(select(User).where(User.id == user_id))
    target_user = res.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if current_user.workspace_id != target_user.workspace_id or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to remove this user")
        
    # Prevent removing oneself if they are the only admin
    if target_user.id == current_user.id:
        admin_res = await db.execute(
            select(User).where(User.workspace_id == target_user.workspace_id, User.role == "admin")
        )
        admins = admin_res.scalars().all()
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin of the workspace")
            
    await db.delete(target_user)
    await db.commit()
    return {"status": "success"}
