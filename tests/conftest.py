import os
os.environ["ENABLE_TELEMETRY"] = "false"
os.environ["TESTING"] = "true"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://driftline:driftline@127.0.0.1:5433/driftline_db"

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from main import app
from src.db.session import get_db, DATABASE_URL
from src.auth.dependencies import get_current_user
from src.auth.models import User

@pytest.fixture(autouse=True)
async def override_db_dependency():
    test_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        
        TestAsyncSessionLocal = async_sessionmaker(
            bind=conn, 
            class_=AsyncSession, 
            expire_on_commit=False, 
            autoflush=False,
            join_transaction_mode="create_savepoint"
        )
        
        async def _get_test_db():
            async with TestAsyncSessionLocal() as session:
                try:
                    yield session
                finally:
                    await session.close()
                    
        app.dependency_overrides[get_db] = _get_test_db
        
        async def _get_mock_user():
            return User(id=1, email="test@example.com", workspace_id=1, role="member", is_active=True)
            
        app.dependency_overrides[get_current_user] = _get_mock_user
        
        try:
            yield
        finally:
            app.dependency_overrides.clear()
            await trans.rollback()

@pytest.fixture
async def db() -> AsyncSession:
    db_gen = app.dependency_overrides[get_db]()
    session = await anext(db_gen)
    try:
        yield session
    finally:
        pass

