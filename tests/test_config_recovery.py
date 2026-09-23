import json
import logging

import pytest

from whisperapp.config_manager import ConfigManager, DEFAULT_SETTINGS


@pytest.mark.parametrize("raw", ["[]", '"hello"', "42", "null", "{bad json"])
def test_invalid_settings_are_backed_up_and_defaults_loaded(tmp_path, monkeypatch, raw):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("WHISPER_API_KEY", raising=False)
    config_dir = tmp_path / ".whisperapp"
    config_dir.mkdir()
    path = config_dir / "config.json"
    path.write_text(raw, encoding="utf-8")

    settings = ConfigManager()

    assert settings.get_settings()["model"] == DEFAULT_SETTINGS["model"]
    assert path.read_text(encoding="utf-8") == raw
    backups = list(config_dir.glob("config.invalid-*.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == raw


def test_failed_atomic_write_keeps_last_valid_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("WHISPER_API_KEY", raising=False)
    config = ConfigManager()
    original = config.config_path.read_bytes()

    def fail_replace(src, dst):
        raise OSError("simulated interrupted replacement")

    monkeypatch.setattr("whisperapp.config_manager.os.replace", fail_replace)
    with pytest.raises(OSError):
        config.save_settings({"language": "fr"})

    assert config.config_path.read_bytes() == original


def test_api_key_is_encrypted_and_never_logged(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("WHISPER_API_KEY", raising=False)
    secret = "sk-test-must-not-appear"
    with caplog.at_level(logging.WARNING):
        config = ConfigManager()
        config.set_api_key(secret)
        config.config_path.write_text("not json", encoding="utf-8")
        ConfigManager()
    assert secret.encode() not in config.config_path.read_bytes()
    assert secret not in caplog.text
