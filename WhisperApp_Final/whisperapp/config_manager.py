import json
import os
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken


DEFAULT_SETTINGS: Dict[str, Any] = {
    "api_key": "",
    "model": "whisper-1",
    "language": "en",
    "hotkey": "ctrl+shift+space",
    "auto_copy": True,
    "show_notifications": True,
    "audio_device": "default",
}


class ConfigManager:
    def __init__(self) -> None:
        self.config_dir = Path.home() / ".whisperapp"
        self.config_path = self.config_dir / "config.json"
        self.key_path = self.config_dir / "key.key"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(self._load_or_create_key())
        self._settings = self._load_settings()
        self._hydrate_api_key_from_env_if_missing()

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        return key

    def _load_settings(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            settings = dict(DEFAULT_SETTINGS)
            self._write_settings(settings)
            return settings
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            settings = dict(DEFAULT_SETTINGS)
            settings.update(data)
            return settings
        except (json.JSONDecodeError, OSError):
            settings = dict(DEFAULT_SETTINGS)
            self._write_settings(settings)
            return settings

    def _write_settings(self, settings: Dict[str, Any]) -> None:
        self.config_path.write_text(
            json.dumps(settings, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""

    def _hydrate_api_key_from_env_if_missing(self) -> None:
        if self.get_api_key():
            return
        env_key = os.getenv("WHISPER_API_KEY", "").strip()
        if env_key:
            self.set_api_key(env_key)

    def get_settings(self) -> Dict[str, Any]:
        settings = dict(self._settings)
        settings["api_key"] = self.get_api_key()
        return settings

    def save_settings(self, settings: Dict[str, Any]) -> None:
        updated = dict(self._settings)
        updated.update(settings)

        if "api_key" in settings:
            api_key = (settings.get("api_key") or "").strip()
            updated["api_key"] = self._encrypt(api_key) if api_key else ""

        self._settings = updated
        self._write_settings(self._settings)

    def get_api_key(self) -> str:
        encrypted = self._settings.get("api_key", "")
        if not encrypted:
            return ""
        return self._decrypt(encrypted)

    def set_api_key(self, api_key: str) -> None:
        self.save_settings({"api_key": api_key})
