import json

from whisperapp.config_manager import ConfigManager


def test_existing_install_migrates_without_losing_credentials_or_preferences(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("WHISPER_API_KEY", raising=False)
    config = ConfigManager()
    config.save_settings({"api_key": "test-secret", "language": "fr", "hotkey": "ctrl+alt+space"})
    data = json.loads(config.config_path.read_text())
    data.pop("transcription_model_migration")
    data["model"] = "whisper-1"
    config.config_path.write_text(json.dumps(data))

    migrated = ConfigManager()
    settings = migrated.get_settings()
    assert settings["model"] == "gpt-transcribe"
    assert settings["api_key"] == "test-secret"
    assert settings["language"] == "fr"
    assert settings["hotkey"] == "ctrl+alt+space"
    stored = json.loads(config.config_path.read_text())
    assert stored["api_key"] == data["api_key"]
    assert stored["model"] == "gpt-transcribe"

    migrated.save_settings({"model": "whisper-1"})
    assert ConfigManager().get_settings()["model"] == "whisper-1"


def test_custom_model_is_preserved_on_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("WHISPER_API_KEY", raising=False)
    config = ConfigManager()
    config.config_path.write_text(json.dumps({"model": "custom-model"}))
    assert ConfigManager().get_settings()["model"] == "custom-model"
