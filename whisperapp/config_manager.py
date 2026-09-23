import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken


DEFAULT_TRANSCRIPTION_MODEL = "gpt-transcribe"
logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "api_key": "",
    "model": DEFAULT_TRANSCRIPTION_MODEL,
    "transcription_model_migration": 1,
    "language": "en",
    "hotkey": "ctrl+shift+space",
    "auto_copy": True,
    "show_notifications": True,
    "audio_device": "default",
}


class ConfigManager:
    def __init__(self) -> None:
        appdata = os.getenv("APPDATA")
        self.config_dir = Path(appdata) / ".whisperapp" if appdata else Path.home() / ".whisperapp"
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
            if not isinstance(data, dict):
                raise ValueError("top-level JSON value must be an object")
            settings = dict(DEFAULT_SETTINGS)
            settings.update(data)
            # Migrate the old default once; a later explicit fallback choice survives.
            if not data.get("transcription_model_migration"):
                if settings.get("model") == "whisper-1":
                    settings["model"] = DEFAULT_TRANSCRIPTION_MODEL
                settings["transcription_model_migration"] = 1
                self._write_settings(settings)
            return settings
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            self._preserve_invalid_settings()
            logger.warning(
                "Settings file is invalid or unreadable; using defaults in memory (%s)",
                type(exc).__name__,
            )
            return dict(DEFAULT_SETTINGS)

    def _preserve_invalid_settings(self) -> None:
        if not self.config_path.exists():
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.config_dir / f"config.invalid-{stamp}.json"
        try:
            shutil.copy2(self.config_path, backup)
            logger.warning("Preserved invalid settings file at %s", backup)
        except OSError as exc:
            logger.error("Could not preserve invalid settings file (%s)", type(exc).__name__)

    def _write_settings(self, settings: Dict[str, Any]) -> None:
        payload = json.dumps(settings, indent=2, sort_keys=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.config_dir,
                prefix="config.", suffix=".tmp", delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.config_path)
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove temporary settings file")

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

        self._write_settings(updated)
        self._settings = updated

    def get_api_key(self) -> str:
        encrypted = self._settings.get("api_key", "")
        if not encrypted:
            return ""
        return self._decrypt(encrypted)

    def set_api_key(self, api_key: str) -> None:
        self.save_settings({"api_key": api_key})
