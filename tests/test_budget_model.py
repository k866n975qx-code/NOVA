

from __future__ import annotations

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session
from app.db.models.base import Base
from app.db.models.budget import Budget  # noqa: F401  (import ensures model is registered)


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


def test_budgets_table_can_be_created(monkeypatch):
    """
    Basic integration test to ensure the Budget model is wired correctly and
    its table can be created against the current Base metadata.
    """
    engine = _make_engine_sqlite_memory(monkeypatch)

    # This will raise if the model/metadata is misconfigured.
    Base.metadata.create_all(bind=engine)

    inspector = sqlalchemy.inspect(engine)
    tables = inspector.get_table_names()
    assert "budgets" in tables


def test_budgets_table_has_expected_columns(monkeypatch):
    """
    Ensure the budgets table exposes the expected column names, including
    those inherited from BaseModel (id, created_at, updated_at).
    """
    engine = _make_engine_sqlite_memory(monkeypatch)

    Base.metadata.create_all(bind=engine)
    inspector = sqlalchemy.inspect(engine)

    column_names = {col["name"] for col in inspector.get_columns("budgets")}

    expected = {
        "id",
        "created_at",
        "updated_at",
        "source",
        "external_id",
        "name",
        "category",
        "period_start",
        "period_end",
        "limit_amount",
        "currency",
        "is_active",
    }
    assert expected.issubset(column_names)


def test_create_and_query_budget_round_trip(monkeypatch):
    """
    Round-trip test: create a Budget, commit it, and query it back to verify
    that the model works end-to-end with a real SQLAlchemy Session.
    """
    engine = _make_engine_sqlite_memory(monkeypatch)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        budget = Budget(
            source="lunchmoney",
            external_id="bud_123",
            name="Test Groceries Budget",
            category="Groceries",
            period_start=None,
            period_end=None,
            limit_amount=300.00,
            currency="USD",
            is_active=True,
        )
        session.add(budget)
        session.commit()
        session.refresh(budget)

        fetched = session.query(Budget).filter_by(external_id="bud_123").one()

        assert fetched.id == budget.id
        assert fetched.name == "Test Groceries Budget"
        assert fetched.limit_amount == budget.limit_amount
        assert fetched.currency == "USD"
        assert fetched.is_active is True