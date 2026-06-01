import pytest
import os

from backend.core.database import init_db

TEST_DB_PATH = "backend/tests/test_database.sqlite"

@pytest.fixture(autouse=True, scope="session")
def setup_test_db_session():
    import backend.core.database
    import backend.core.match_state
    import asyncio

    orig_db_path = backend.core.database.DB_PATH
    backend.core.database.DB_PATH = TEST_DB_PATH
    backend.core.match_state.DB_PATH = TEST_DB_PATH

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    asyncio.run(init_db())

    yield

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    backend.core.database.DB_PATH = orig_db_path
    backend.core.match_state.DB_PATH = orig_db_path
