import pytest
from backend.core.database import init_db

@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
