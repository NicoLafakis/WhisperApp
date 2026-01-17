/**
 * JARVIS Voice Agent - Settings Modal
 */

import { useState, useEffect } from 'react';
import './electron.d.ts';

export interface UserSettings {
  openaiApiKey: string;
  elevenLabsApiKey: string;
  elevenLabsVoiceId: string;
  wakeWord: string;
  sensitivity: number;
  dailyBudget: number;
  monthlyBudget: number;
  skipSettingsOnStartup: boolean;
  runOnStartup: boolean;
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  isFirstRun: boolean;
}

export default function SettingsModal({ isOpen, onClose, isFirstRun }: SettingsModalProps) {
  const [settings, setSettings] = useState<UserSettings>({
    openaiApiKey: '',
    elevenLabsApiKey: '',
    elevenLabsVoiceId: 'EXAVITQu4MsJ5X4xQvF9',
    wakeWord: 'jarvis',
    sensitivity: 0.5,
    dailyBudget: 1.0,
    monthlyBudget: 30.0,
    skipSettingsOnStartup: false,
    runOnStartup: false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    if (isOpen) {
      window.electronAPI.getSettings().then((savedSettings) => {
        if (savedSettings) {
          setSettings(prev => ({ ...prev, ...savedSettings }));
        }
      });
    }
  }, [isOpen]);

  const handleChange = (field: keyof UserSettings, value: string | number | boolean) => {
    setSettings(prev => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleSave = async () => {
    // Validate required fields
    if (!settings.openaiApiKey.trim()) {
      setError('OpenAI API key is required');
      return;
    }

    // Basic API key format validation
    if (!settings.openaiApiKey.startsWith('sk-')) {
      setError('OpenAI API key should start with "sk-"');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      // Cast to Record<string, unknown> for IPC compatibility
      await window.electronAPI.saveSettings(settings as unknown as Record<string, unknown>);
      onClose();
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to save settings';
      setError(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="settings-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <div className="settings-modal">
        <div className="settings-header">
          <h2 id="settings-title">{isFirstRun ? 'Welcome to JARVIS' : 'Settings'}</h2>
          {isFirstRun && (
            <p className="settings-subtitle">Configure your voice assistant to get started</p>
          )}
        </div>

        <div className="settings-content">
          {error && (
            <div className="settings-error" role="alert">
              {error}
            </div>
          )}

          <section className="settings-section" aria-labelledby="api-keys-heading">
            <h3 id="api-keys-heading">API Keys</h3>

            <div className="settings-field">
              <label htmlFor="openai-key">OpenAI API Key *</label>
              <div className="input-with-toggle">
                <input
                  id="openai-key"
                  type={showApiKey ? 'text' : 'password'}
                  value={settings.openaiApiKey}
                  onChange={(e) => handleChange('openaiApiKey', e.target.value)}
                  placeholder="sk-..."
                  autoComplete="off"
                  aria-required="true"
                  aria-describedby="openai-key-hint"
                />
                <button
                  type="button"
                  className="toggle-visibility"
                  onClick={() => setShowApiKey(!showApiKey)}
                  aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
                >
                  {showApiKey ? '🙈' : '👁️'}
                </button>
              </div>
              <span id="openai-key-hint" className="field-hint">
                Required for voice recognition and responses.{' '}
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hint-link"
                >
                  Get your API key
                </a>
              </span>
            </div>

            <div className="settings-field">
              <label htmlFor="elevenlabs-key">ElevenLabs API Key</label>
              <input
                id="elevenlabs-key"
                type="password"
                value={settings.elevenLabsApiKey}
                onChange={(e) => handleChange('elevenLabsApiKey', e.target.value)}
                placeholder="Optional - for premium voice"
                autoComplete="off"
                aria-describedby="elevenlabs-key-hint"
              />
              <span id="elevenlabs-key-hint" className="field-hint">
                Optional - enables higher quality voice synthesis
              </span>
            </div>
          </section>

          <section className="settings-section" aria-labelledby="budget-heading">
            <h3 id="budget-heading">Budget Limits</h3>

            <div className="settings-row">
              <div className="settings-field">
                <label htmlFor="daily-budget">Daily Budget ($)</label>
                <input
                  id="daily-budget"
                  type="number"
                  min="0.10"
                  step="0.10"
                  value={settings.dailyBudget}
                  onChange={(e) => handleChange('dailyBudget', parseFloat(e.target.value) || 0.10)}
                  aria-describedby="daily-budget-hint"
                />
              </div>

              <div className="settings-field">
                <label htmlFor="monthly-budget">Monthly Budget ($)</label>
                <input
                  id="monthly-budget"
                  type="number"
                  min="1"
                  step="1"
                  value={settings.monthlyBudget}
                  onChange={(e) => handleChange('monthlyBudget', parseFloat(e.target.value) || 1)}
                />
              </div>
            </div>
            <span id="daily-budget-hint" className="field-hint">
              JARVIS will switch to efficient mode when approaching budget limits
            </span>
          </section>

          <section className="settings-section" aria-labelledby="startup-heading">
            <h3 id="startup-heading">Startup</h3>

            <div className="settings-checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={settings.runOnStartup}
                  onChange={(e) => handleChange('runOnStartup', e.target.checked)}
                />
                Run JARVIS when Windows starts
              </label>
            </div>

            <div className="settings-checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={settings.skipSettingsOnStartup}
                  onChange={(e) => handleChange('skipSettingsOnStartup', e.target.checked)}
                />
                Skip this screen on startup
              </label>
            </div>
          </section>
        </div>

        <div className="settings-footer">
          {!isFirstRun && (
            <button
              type="button"
              className="settings-btn secondary"
              onClick={onClose}
            >
              Cancel
            </button>
          )}
          <button
            type="button"
            className="settings-btn primary"
            onClick={handleSave}
            disabled={saving}
            aria-busy={saving}
          >
            {saving ? 'Saving...' : (isFirstRun ? 'Get Started' : 'Save')}
          </button>
        </div>
      </div>
    </div>
  );
}
