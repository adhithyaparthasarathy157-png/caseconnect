"""Mandatory database isolation for every pytest test in this repository."""

import os
from pathlib import Path

import pytest

TEST_DATABASE_PATH = (Path(__file__).resolve().parent.parent / ".pytest-caseconnect.db").resolve()
TEST_DATABASE_URL = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"

# Pytest imports this configuration before test modules import the application.
# Do not use an inherited deployment URL, even if one was supplied by a shell.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-that-is-longer-than-thirty-two-characters")


def assert_isolated_test_database_url(database_url: str) -> None:
    """Reject anything except this repository's dedicated SQLite test file."""
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("Tests require the dedicated SQLite test database; non-SQLite URLs are forbidden")
    resolved_path = Path(database_url[len("sqlite:///"):]).resolve()
    if resolved_path != TEST_DATABASE_PATH:
        raise RuntimeError("Tests may only use .pytest-caseconnect.db; demo and deployment databases are forbidden")


def _assert_active_engine_is_safe() -> None:
    from app.config import get_settings
    from app.database import engine

    assert_isolated_test_database_url(get_settings().database_url)
    assert_isolated_test_database_url(str(engine.url))


def pytest_configure() -> None:
    _assert_active_engine_is_safe()


@pytest.fixture(autouse=True)
def isolated_database():
    """Recreate only the guarded test schema around every test, even on errors."""
    from app.database import Base, engine

    _assert_active_engine_is_safe()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        _assert_active_engine_is_safe()
        Base.metadata.drop_all(engine)
