/**
 * JARVIS Voice Agent - Settings Modal
 */

import { useState, useEffect } from 'react';

const { ipcRenderer } = window.require('electron');

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

  useEffect(() => {
    if (isOpen) {
      ipcRenderer.invoke('settings:get').then((savedSettings: Partial<UserSettings>) => {
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

    setSaving(true);
    setError(null);

    try {
      await ipcRenderer.invoke('settings:save', settings);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="settings-overlay">
      <div className="settings-modal">
        <div className="settings-header">
          <h2>{isFirstRun ? 'Welcome to JARVIS' : 'Settings'}</h2>
          {isFirstRun && (
            <p className="settings-subtitle">Configure your voice assistant to get started</p>
          )}
        </div>

        <div className="settings-content">
          {error && <div className="settings-error">{error}</div>}

          <div className="settings-section">
            <h3>API Keys</h3>

            <div className="settings-field">
              <label>OpenAI API Key *</label>
              <input
                type="password"
                value={settings.openaiApiKey}
                onChange={(e) => handleChange('openaiApiKey', e.target.value)}
                placeholder="sk-..."
              />
              <span className="field-hint">Required for voice recognition and responses</span>
            </div>

            <div className="settings-field">
              <label>ElevenLabs API Key</label>
              <input
                type="password"
                value={settings.elevenLabsApiKey}
                onChange={(e) => handleChange('elevenLabsApiKey', e.target.value)}
                placeholder="Optional - for premium voice"
              />
              <span className="field-hint">Optional - enables higher quality voice</span>
            </div>
          </div>

          <div className="settings-section">
            <h3>Wake Word</h3>

            <div className="settings-field">
              <label>Keyword</label>
              <input
                type="text"
                value={settings.wakeWord}
                onChange={(e) => handleChange('wakeWord', e.target.value)}
                placeholder="jarvis"
              />
            </div>

            <div className="settings-field">
              <label>Sensitivity: {settings.sensitivity.toFixed(1)}</label>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.1"
                value={settings.sensitivity}
                onChange={(e) => handleChange('sensitivity', parseFloat(e.target.value))}
              />
              <span className="field-hint">Higher = more sensitive, may cause false triggers</span>
            </div>
          </div>

          <div className="settings-section">
            <h3>Budget Limits</h3>

            <div className="settings-row">
              <div className="settings-field">
                <label>Daily Budget ($)</label>
                <input
                  type="number"
                  min="0.10"
                  step="0.10"
                  value={settings.dailyBudget}
                  onChange={(e) => handleChange('dailyBudget', parseFloat(e.target.value))}
                />
              </div>

              <div className="settings-field">
                <label>Monthly Budget ($)</label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={settings.monthlyBudget}
                  onChange={(e) => handleChange('monthlyBudget', parseFloat(e.target.value))}
                />
              </div>
            </div>
          </div>

          <div className="settings-section">
            <h3>Startup</h3>

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
          </div>
        </div>

        <div className="settings-footer">
          {!isFirstRun && (
            <button className="settings-btn secondary" onClick={onClose}>
              Cancel
            </button>
          )}
          <button
            className="settings-btn primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : (isFirstRun ? 'Get Started' : 'Save')}
          </button>
        </div>
      </div>
    </div>
  );
}
