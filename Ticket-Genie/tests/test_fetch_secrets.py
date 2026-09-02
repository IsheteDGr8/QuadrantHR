from __future__ import annotations

from pathlib import Path

from fetch_secrets import format_vault_url, load_existing_env, save_env_file


def test_format_vault_url() -> None:
    assert (
        format_vault_url("kv-app-prod-12345")
        == "https://kv-app-prod-12345.vault.azure.net/"
    )
    assert format_vault_url("https://group-1.vault.azure.net") == (
        "https://group-1.vault.azure.net/"
    )
    assert format_vault_url("https://group-1.vault.azure.net/") == (
        "https://group-1.vault.azure.net/"
    )


def test_save_and_load_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"

    secrets = {
        "DB_ADMIN_PASSWORD": "SecretPassword123!",
        "API_KEY": "abc key with spaces",
    }

    save_env_file(env_file, secrets)

    loaded = load_existing_env(env_file)
    assert loaded["DB_ADMIN_PASSWORD"] == "SecretPassword123!"
    assert loaded["API_KEY"] == '"abc key with spaces"'
