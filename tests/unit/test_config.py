from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_desk.core.config import Settings


def test_settings_can_be_injected_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", ".cache/test-huggingface")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "8")

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.app_version == "9.9.9"
    assert settings.embedding_cache_dir == Path(".cache/test-huggingface")
    assert settings.retrieval_top_k == 8


def test_retrieval_top_k_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RETRIEVAL_TOP_K", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
