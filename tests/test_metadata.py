"""Tests for immutable application metadata."""

from dataclasses import FrozenInstanceError

import pytest

from marktwert import APPLICATION


def test_application_metadata_is_complete() -> None:
    assert APPLICATION.name == "MarktWert"
    assert APPLICATION.organization == "MarktWert"
    assert APPLICATION.version == "0.1.0"


def test_application_metadata_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        APPLICATION.name = "Changed"  # type: ignore[misc]
