import os

import pytest
from sqlalchemy import func, select

from app.database import SessionLocal, engine
from app.models import Institution
from tests.conftest import TEST_DATABASE_URL, assert_isolated_test_database_url


def test_isolation_guard_rejects_demo_and_non_sqlite_urls():
    assert_isolated_test_database_url(TEST_DATABASE_URL)
    with pytest.raises(RuntimeError, match="demo and deployment"):
        assert_isolated_test_database_url("sqlite:///./caseconnect.db")
    with pytest.raises(RuntimeError, match="non-SQLite"):
        assert_isolated_test_database_url("postgresql+psycopg://user:password@host/caseconnect")


def test_active_test_engine_is_dedicated_and_starts_empty():
    assert str(engine.url) == TEST_DATABASE_URL
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Institution.id))) == 0


def test_failure_cleanup_probe():
    """Executed separately with CASECONNECT_TEST_FAILURE_PROBE=1 as a safety probe."""
    if os.environ.get("CASECONNECT_TEST_FAILURE_PROBE") != "1":
        return
    with SessionLocal() as db:
        db.add(Institution(
            permanent_id="FAILURE-PROBE", permanent_id_verified=False,
            name="Failure Probe Institution", normalized_name="failure probe institution",
            institution_type="College", region="North", status="Active",
        ))
        db.commit()
    raise RuntimeError("intentional test-isolation cleanup probe")
