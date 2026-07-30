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
    TestAsyncSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
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
    yield
    app.dependency_overrides.clear()
    await test_engine.dispose()
