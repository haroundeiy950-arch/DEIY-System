"""SQLAlchemy engine/session management (SQLite by default, Postgres-ready)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        kwargs: dict = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url or url in {"sqlite://", "sqlite:///"}:
                kwargs["poolclass"] = StaticPool
            else:
                from sqlalchemy.engine import make_url

                database_path = make_url(url).database
                if database_path:
                    from pathlib import Path

                    Path(database_path).expanduser().resolve().parent.mkdir(
                        parents=True, exist_ok=True
                    )
        self.url = url
        self.engine = create_engine(url, **kwargs)

        if url.startswith("sqlite"):
            from sqlalchemy import event

            @event.listens_for(self.engine, "connect")
            def _sqlite_pragmas(dbapi_connection, connection_record):  # pragma: no cover
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA busy_timeout=5000")
                    cursor.execute("PRAGMA foreign_keys=ON")
                finally:
                    cursor.close()

        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
            future=True,
        )

    def create_all(self) -> None:
        # Imported here so the models module can import ``Base`` without a cycle.
        from deiy import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        from deiy import models  # noqa: F401

        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional scope: commits on success, rolls back on error."""

        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dependency(self) -> Iterator[Session]:
        """FastAPI dependency variant (no implicit commit)."""

        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
