"""Transaction-scoped SQLAlchemy unit of work."""

from types import TracebackType

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from marktwert.infrastructure.persistence.search_repository import (
    SqlAlchemySaleSearchRepository,
)
from marktwert.infrastructure.persistence.repositories import (
    SqlAlchemySaleObservationRepository,
    SqlAlchemyTrackedProductRepository,
)


class SqlAlchemyUnitOfWork:
    """Coordinate repositories within one atomic database transaction."""

    tracked_products: SqlAlchemyTrackedProductRepository
    sale_observations: SqlAlchemySaleObservationRepository
    sale_search: SqlAlchemySaleSearchRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Create an unopened unit of work."""
        self._session_factory = session_factory
        self._session: Session | None = None
        self._committed = False

    @classmethod
    def factory_for(
        cls,
        engine: Engine,
    ) -> "SqlAlchemyUnitOfWorkFactory":
        """Create a reusable unit-of-work factory for an engine."""
        return SqlAlchemyUnitOfWorkFactory(
            sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=True,
            )
        )

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        """Open a transaction and initialize repositories."""
        if self._session is not None:
            message = "unit of work is already active"
            raise RuntimeError(message)
        self._session = self._session_factory()
        self._committed = False
        self.tracked_products = SqlAlchemyTrackedProductRepository(self._session)
        self.sale_observations = SqlAlchemySaleObservationRepository(self._session)
        self.sale_search = SqlAlchemySaleSearchRepository(self._session)
        return self

    def commit(self) -> None:
        """Commit all changes in the transaction."""
        self._require_session().commit()
        self._committed = True

    def rollback(self) -> None:
        """Roll back all changes in the transaction."""
        self._require_session().rollback()

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back uncommitted work and close the session."""
        del exception_type, exception, traceback
        session = self._require_session()
        try:
            if not self._committed:
                session.rollback()
        finally:
            session.close()
            self._session = None

    def _require_session(self) -> Session:
        if self._session is None:
            message = "unit of work is not active"
            raise RuntimeError(message)
        return self._session


class SqlAlchemyUnitOfWorkFactory:
    """Create independent SQLAlchemy units of work."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Store the shared thread-safe session factory."""
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        """Create an unopened unit of work."""
        return SqlAlchemyUnitOfWork(self._session_factory)
