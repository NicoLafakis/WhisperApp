/**
 * Type declarations for the Electron API exposed via preload
 */

export interface ElectronAPI {
  // Agent control
  startAgent: () => Promise<{ success: boolean; error?: string }>;
  stopAgent: () => Promise<void>;
  getAgentState: () => Promise<import('../shared/types').AgentState | null>;
  triggerWakeWord: () => Promise<void>;

  // Settings
  checkFirstRun: () => Promise<{ isFirstRun: boolean; showSettings: boolean }>;
  getSettings: () => Promise<Partial<UserSettings>>;
  saveSettings: (settings: Record<string, unknown>) => Promise<boolean>;

  // Config & Metrics
  getConfig: () => Promise<Record<string, unknown>>;
  getCostMetrics: () => Promise<import('../shared/types').CostMetrics | null>;

  // Event listeners - return cleanup functions
  onStatusChanged: (callback: (state: import('../shared/types').AgentState) => void) => () => void;
  onMessage: (callback: (message: { role: string; text: string }) => void) => () => void;
  onCostUpdated: (callback: (metrics: import('../shared/types').CostMetrics) => void) => () => void;
  onError: (callback: (error: { message: string }) => void) => () => void;
  onAudioPlaying: (callback: (data: { intensity: number }) => void) => () => void;
  onAudioStopped: (callback: () => void) => () => void;

  // Cleanup
  removeAllListeners: () => void;
}

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

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
