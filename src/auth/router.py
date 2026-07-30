from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from src.db.session import get_db
from src.auth.models import User
from src.db.models import Workspace
from src.auth.schemas import UserCreate, UserRead, Token
from src.auth.security import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserRead)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    # Check if user exists
    res = await db.execute(select(User).where(User.email == user_in.email))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    
    # Always create a new workspace upon registration
    workspace = Workspace(name=user_in.workspace_name)
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
        
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        workspace_id=workspace.id,
        role=user_in.role
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Any:
    res = await db.execute(select(User).where(User.email == form_data.username))
    user = res.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)) -> Any:
    return current_user
