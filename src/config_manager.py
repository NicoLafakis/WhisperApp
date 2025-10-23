"""
Configuration manager for WhisperApp
Handles loading, saving, and encrypting settings
"""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
import base64


class ConfigManager:
    """Manages application configuration and secure storage"""

    def __init__(self):
        self.config_dir = Path.home() / '.whisperapp'
        self.config_file = self.config_dir / 'config.json'
        self.key_file = self.config_dir / 'key.key'
        self.config = self._load_config()

    def _ensure_config_dir(self):
        """Ensure config directory exists"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _get_encryption_key(self):
        """Get or create encryption key"""
        self._ensure_config_dir()
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key

    def _encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        key = self._get_encryption_key()
        f = Fernet(key)
        return f.encrypt(data.encode()).decode()

    def _decrypt(self, data: str) -> str:
        """Decrypt sensitive data"""
        try:
            key = self._get_encryption_key()
            f = Fernet(key)
            return f.decrypt(data.encode()).decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return ""

    def _load_config(self):
        """Load configuration from file"""
        default_config = {
            'api_key': '',
            'model': 'whisper-1',
            'language': 'en',
            'hotkey': 'ctrl+shift+space',
            'auto_copy': True,
            'show_notifications': True,
            'audio_device': 'default'
        }

        if not self.config_file.exists():
            return default_config

        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Decrypt API key if present
                if config.get('api_key'):
                    config['api_key'] = self._decrypt(config['api_key'])
                return {**default_config, **config}
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config

    def save_config(self):
        """Save configuration to file"""
        self._ensure_config_dir()
        config_to_save = self.config.copy()

        # Encrypt API key before saving
        if config_to_save.get('api_key'):
            config_to_save['api_key'] = self._encrypt(config_to_save['api_key'])

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self.save_config()

    def get_api_key(self):
        """Get OpenAI API key"""
        return self.config.get('api_key', '')

    def set_api_key(self, api_key):
        """Set OpenAI API key"""
        self.set('api_key', api_key)
