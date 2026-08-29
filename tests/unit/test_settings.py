from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_settings_include_governed_local_runtime_hosts() -> None:
    settings = Settings()

    assert "render.dev.lotus" in settings.allowed_hosts
    assert "host.docker.internal" in settings.allowed_hosts
    assert "*" not in settings.allowed_hosts


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
    with pytest.raises(ValidationError, match="loses accepted render jobs on restart"):
        Settings(require_persistent_render_store=True, render_store_path=":memory:")


@pytest.mark.parametrize("environment", ["production", "uat", "staging", "test"])
def test_memory_store_is_rejected_outside_development(environment: str) -> None:
    """Persistence is derived from the environment, not opted into (#83).

    An accepted render job lives only in the store until a worker picks it up, so a
    non-development deployment must not be able to configure job loss silently.
    """

    with pytest.raises(ValidationError, match="loses accepted render jobs on restart"):
        Settings(environment=environment, render_store_path=":memory:")


def test_memory_store_is_allowed_only_in_development_without_the_flag() -> None:
    settings = Settings(environment="development", render_store_path=":memory:")
    assert settings.persistent_render_store_required is False


def test_development_can_still_opt_into_required_persistence() -> None:
    with pytest.raises(ValidationError, match="loses accepted render jobs on restart"):
        Settings(
            environment="development",
            require_persistent_render_store=True,
            render_store_path=":memory:",
        )


def test_durable_store_path_is_accepted_in_every_environment() -> None:
    for environment in ("development", "production"):
        settings = Settings(environment=environment, render_store_path="data/store.sqlite3")
        assert settings.render_store_path == "data/store.sqlite3"
