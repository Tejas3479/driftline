from datetime import timedelta
import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from src.db.session import get_db
from src.auth.models import User
from src.db.models import Workspace
from src.auth.schemas import UserCreate, UserRead, Token
from src.auth.security import (
    get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_NAME, COOKIE_SECURE, COOKIE_HTTPONLY, COOKIE_SAMESITE, COOKIE_MAX_AGE
)
from src.auth.dependencies import get_current_user
from src.limiter import limiter
from fastapi import Response

from src.auth.service import register_user, authenticate_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserRead)
@limiter.limit("5/minute")
async def register(request: Request, user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    logger.info("user_registration_attempt", email=user_in.email)
    try:
        user = await register_user(db, user_in)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Any:
    logger.info("user_login_attempt", email=form_data.username)
    user = await authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE
    )
    return {"status": "ok"}

@router.post("/logout")
async def logout(response: Response) -> Any:
    response.delete_cookie(key=COOKIE_NAME, httponly=COOKIE_HTTPONLY, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    return {"status": "ok"}

@router.get("/me", response_model=UserRead)
@limiter.limit("30/minute")
async def read_current_user(request: Request, current_user: User = Depends(get_current_user)) -> Any:
    return current_user
