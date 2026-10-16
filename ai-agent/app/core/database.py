"""Read-only access to the backend's database.

Two things make this module the whole of the service's write-safety
story:

- `create_all` is never called. The agent service owns no schema; the
  backend is the only writer and the only migrator. If a table the agent
  expects is missing, that is a deployment error worth failing on, not
  something to paper over by creating an empty table.
- On Postgres every connection is opened with
  `default_transaction_read_only=on`, passed as a libpq connection
  option, so an accidental INSERT/UPDATE inside a tool raises instead of
  mutating the family's books. That guarantee lives here rather than in
  a code-review convention.

  It is deliberately *not* done with a `SET SESSION CHARACTERISTICS`
  statement on connect, which is the obvious approach and does not work:
  `SET` is itself transactional, psycopg2 opens a transaction on first
  execute, and the connection pool's rollback on check-in silently
  reverts it. A libpq option is applied during connection setup and
  survives every rollback.

  For defence that does not depend on this process at all, point
  `DATABASE_URL` at a Postgres role with only `SELECT` granted. This
  module protects against our own bugs; a read-only role protects
  against anything.

SQLite is supported for local development only, where the same guarantee
is a URI flag rather than a session setting.
"""
from collections.abc import Iterator

from sqlmodel import Session, create_engine

from app.core.config import settings


def _build_engine():
    if settings.is_sqlite:
        # `mode=ro` is SQLite's own read-only open. It needs the URI form,
        # and a file that does not exist yet is an error rather than an
        # empty database — which is the honest behaviour here.
        url = settings.database_url
        path = url.split("sqlite:///", 1)[-1]
        return create_engine(
            f"sqlite:///file:{path}?mode=ro&uri=true",
            echo=False,
            connect_args={"check_same_thread": False, "uri": True},
        )
    return create_engine(
        settings.database_url,
        echo=False,
        # PaaS providers recycle idle connections; ping before use.
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


engine = _build_engine()



def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
