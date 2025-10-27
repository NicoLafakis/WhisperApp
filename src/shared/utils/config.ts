/**
 * JARVIS Voice Agent - Configuration Manager
 */

import { AppConfig } from '../types';
import * as dotenv from 'dotenv';

dotenv.config();

export class ConfigManager {
  private config: AppConfig;

  constructor() {
    this.config = this.loadConfig();
  }

  private loadConfig(): AppConfig {
    return {
      openai: {
        apiKey: process.env.OPENAI_API_KEY || '',
      },
      elevenlabs: {
        apiKey: process.env.ELEVENLABS_API_KEY || '',
        voiceId: process.env.ELEVENLABS_VOICE_ID || 'EXAVITQu4MsJ5X4xQvF9',
      },
      audio: {
        sampleRate: parseInt(process.env.SAMPLE_RATE || '16000'),
        channels: parseInt(process.env.AUDIO_CHANNELS || '1'),
        bitDepth: 16,
      },
      wakeWord: {
        keyword: process.env.WAKE_WORD || 'jarvis',
        sensitivity: parseFloat(process.env.WAKE_WORD_SENSITIVITY || '0.5'),
      },
      routing: {
        defaultMode: (process.env.DEFAULT_MODE as 'premium' | 'efficient') || 'premium',
        dailyBudget: parseFloat(process.env.DAILY_BUDGET_USD || '1.00'),
        monthlyBudget: parseFloat(process.env.MONTHLY_BUDGET_USD || '30.00'),
        peakHoursStart: parseInt(process.env.PEAK_HOURS_START || '9'),
        peakHoursEnd: parseInt(process.env.PEAK_HOURS_END || '17'),
      },
      voice: {
        name: 'alloy',
        speed: 1.0,
      },
      security: {
        requireConfirmation: [
          'delete_file',
          'modify_system_settings',
          'uninstall_application',
          'modify_registry',
        ],
        blocked: [
          'access_credentials',
          'modify_admin_protected',
          'run_arbitrary_powershell',
        ],
      },
    };
  }

  getConfig(): AppConfig {
    return { ...this.config };
  }

  updateConfig(updates: Partial<AppConfig>) {
    this.config = {
      ...this.config,
      ...updates,
    };
  }

  get openaiApiKey(): string {
    return this.config.openai.apiKey;
  }

  get audioConfig() {
    return this.config.audio;
  }

  get routingConfig() {
    return this.config.routing;
  }
}

export const configManager = new ConfigManager();
