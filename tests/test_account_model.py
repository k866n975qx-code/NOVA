

from __future__ import annotations

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session
from app.db.models.base import Base
from app.db.models.account import Account  # noqa: F401  (import ensures model is registered)


def _reset_db_cache() -> None:
    """
    Helper to reset module-level engine/session caches between tests.
    """
    setattr(db_session, "_ENGINE", None)
    setattr(db_session, "_SESSION_LOCAL", None)


def _make_engine_sqlite_memory(monkeypatch) -> Engine:
    """
    Create a fresh in-memory SQLite engine using Nova's DB session helper.
    """
    _reset_db_cache()
    monkeypatch.setenv("NOVA_DATABASE_URL", "sqlite:///:memory:")
    return db_session.get_engine(max_retries=1)


def test_accounts_table_can_be_created(monkeypatch):
    """
    Basic integration test to ensure the Account model is wired correctly and
    its table can be created against the current Base metadata.
    """
    engine = _make_engine_sqlite_memory(monkeypatch)

    # This will raise if the model/metadata is misconfigured.
    Base.metadata.create_all(bind=engine)

    inspector = sqlalchemy.inspect(engine)
    tables = inspector.get_table_names()
    assert "accounts" in tables


def test_accounts_table_has_expected_columns(monkeypatch):
    """
    Ensure the accounts table exposes the expected column names, including
    those inherited from BaseModel (id, created_at, updated_at).
    """
    engine = _make_engine_sqlite_memory(monkeypatch)

    Base.metadata.create_all(bind=engine)
    inspector = sqlalchemy.inspect(engine)

    column_names = {col["name"] for col in inspector.get_columns("accounts")}

    expected = {
        "id",
        "created_at",
        "updated_at",
        "source",
        "external_id",
        "name",
        "type",
        "subtype",
        "currency",
        "is_active",
        "is_excluded",
        "institution_name",
        "last_synced_at",
    }
    assert expected.issubset(column_names)


def test_create_and_query_account_round_trip(monkeypatch):
    """
    Round-trip test: create an Account, commit it, and query it back to verify
    that the model works end-to-end with a real SQLAlchemy Session.
    """
    engine = _make_engine_sqlite_memory(monkeypatch)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        account = Account(
            source="lunchmoney",
            external_id="acc_123",
            name="Test Checking",
            type="cash",
            subtype="checking",
            currency="USD",
            is_active=True,
            is_excluded=False,
            institution_name="Test Bank",
        )
        session.add(account)
        session.commit()
        session.refresh(account)

        fetched = session.query(Account).filter_by(external_id="acc_123").one()

        assert fetched.id == account.id
        assert fetched.name == "Test Checking"
        assert fetched.currency == "USD"
        assert fetched.is_active is True