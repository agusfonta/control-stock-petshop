"""Generic repository with soft-delete (C-02).

Models never expose queries; C-04+ reuses this. Physical deletes are
forbidden by the hard rule "never delete a product with sales" — hence
soft_delete flips activo instead of removing the row.
"""

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")


class Repository(Generic[T]):
    """Minimal data-access wrapper over a Session + model class."""

    def __init__(self, session: Session, model: type[T]) -> None:
        self._session = session
        self._model = model

    def get_by_id(self, entity_id: str) -> T | None:
        """Return the entity by PK, including soft-deleted rows."""
        return self._session.get(self._model, entity_id)

    def list_active(self) -> list[T]:
        """Return rows with activo == True."""
        return (
            self._session.query(self._model)
            .filter(self._model.activo.is_(True))
            .all()
        )

    def soft_delete(self, entity: T) -> T:
        """Logical delete: set activo=False, keep the row. Caller commits."""
        entity.activo = False  # type: ignore[attr-defined]
        self._session.add(entity)
        return entity
