"""Database engine and session factory.

The only module that constructs the SQLAlchemy engine. Everything else
gets a Session through the get_session() FastAPI dependency, so no other
layer needs to know how the connection is configured.
"""
from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


# Additive migrations we can safely run on every startup. Keys are table
# names; values map new column names to a SQL column definition. This is
# meant strictly for tiny, backwards-compatible additions — anything more
# involved should get a proper migration tool.
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "user": {
        "contact_number": "TEXT NOT NULL DEFAULT ''",
        "avatar_url": "TEXT NOT NULL DEFAULT ''",
    },
    # Portfolio links. Nullable with no default, so every existing row
    # stays unlinked and nothing is retroactively counted as a
    # contribution or an EMI. No FK constraint is added here: SQLite
    # can't add one to an existing table, and the service validates the
    # target belongs to the household before writing either column.
    "transaction": {
        "investment_id": "INTEGER",
        "debt_id": "INTEGER",
    },
}


def _apply_additive_columns() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in _ADDITIVE_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name in existing:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))


def init_db() -> None:
    # Import the models package so every table is registered on the
    # metadata before create_all runs.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _apply_additive_columns()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
