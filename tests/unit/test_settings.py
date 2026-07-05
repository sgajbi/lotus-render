from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_settings_rejects_blank_scalar_configuration() -> None:
    with pytest.raises(ValidationError, match="value must not be blank"):
        Settings(service_name=" ")


def test_settings_rejects_blank_tuple_entries() -> None:
    with pytest.raises(ValidationError, match="configuration values must not be blank"):
        Settings(allowed_hosts=("localhost", " "))


def test_settings_requires_default_output_format_to_be_supported() -> None:
    with pytest.raises(
        ValidationError,
        match="default_output_format must be included in supported_output_formats",
    ):
        Settings(default_output_format="html", supported_output_formats=("pdf",))


def test_settings_requires_pdf_output_support() -> None:
    with pytest.raises(ValidationError, match="pdf output support is required"):
        Settings(default_output_format="html", supported_output_formats=("html",))


def test_settings_rejects_memory_store_when_persistence_required() -> None:
    with pytest.raises(ValidationError, match="persistent render store is required"):
        Settings(require_persistent_render_store=True, render_store_path=":memory:")
