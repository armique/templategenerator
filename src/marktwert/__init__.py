"""MarktWert desktop market analytics."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplicationMetadata:
    """Immutable identity displayed by the application shell."""

    name: str
    organization: str
    version: str


APPLICATION = ApplicationMetadata(
    name="MarktWert",
    organization="MarktWert",
    version="0.1.0",
)

__all__ = ["APPLICATION", "ApplicationMetadata"]
