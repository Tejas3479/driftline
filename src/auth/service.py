from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.schemas import UserCreate
from src.auth.security import get_password_hash, verify_password
from src.db.models import Workspace


async def register_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Registers a user and creates a new workspace atomically."""
    # Check if user exists
    res = await db.execute(select(User).where(User.email == user_in.email))
    if res.scalar_one_or_none():
        raise ValueError("The user with this email already exists in the system.")
    
    workspace = Workspace(name=user_in.workspace_name)
    db.add(workspace)
    # We flush so that workspace gets an ID, but we do NOT commit yet
    await db.flush()
        
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        workspace_id=workspace.id,
        role=user_in.role
    )
    db.add(user)
    # Commit the transaction containing both workspace and user
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
