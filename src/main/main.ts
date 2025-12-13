/**
 * JARVIS Voice Agent - Electron Main Process
 */

import { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage } from 'electron';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import Store from 'electron-store';
import { JarvisEngine } from './JarvisEngine';
import { logger } from '../shared/utils/logger';

const execAsync = promisify(exec);

// Settings store
interface UserSettings {
  openaiApiKey: string;
  elevenLabsApiKey: string;
  elevenLabsVoiceId: string;
  wakeWord: string;
  sensitivity: number;
  dailyBudget: number;
  monthlyBudget: number;
  skipSettingsOnStartup: boolean;
  runOnStartup: boolean;
  hasCompletedSetup: boolean;
}

const settingsStore = new Store<UserSettings>({
  defaults: {
    openaiApiKey: '',
    elevenLabsApiKey: '',
    elevenLabsVoiceId: 'EXAVITQu4MsJ5X4xQvF9',
    wakeWord: 'jarvis',
    sensitivity: 0.5,
    dailyBudget: 1.0,
    monthlyBudget: 30.0,
    skipSettingsOnStartup: false,
    runOnStartup: false,
    hasCompletedSetup: false,
  },
});

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let jarvisEngine: JarvisEngine | null = null;
let isSetupComplete: boolean = false;

// Audio mute state
let isSystemMuted: boolean = false;
let previousVolume: number = 50;
let autoMuteEnabled: boolean = true;

function createWindow() {
  // Determine if we should show the window on startup
  const hasCompletedSetup = settingsStore.get('hasCompletedSetup');
  const skipSettings = settingsStore.get('skipSettingsOnStartup');
  const shouldShowWindow = !hasCompletedSetup || !skipSettings;

  mainWindow = new BrowserWindow({
    width: 400,
    height: 600,
    show: shouldShowWindow,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Center window if showing
  if (shouldShowWindow) {
    mainWindow.center();
  }

  // Load the app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:3000');
    // DevTools disabled by default - uncomment to debug:
    // mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('blur', () => {
    // Only auto-hide if setup is complete
    if (mainWindow && isSetupComplete) {
      mainWindow.hide();
    }
  });
}

function createTray() {
  // Create a 16x16 tray icon - simple "J" on solid background
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAC9SURBVDhPrZLBDYAgDEWLG7iBI+gIjuAIjuAojuAGjqCx/0OKxIgxetL0tf9BoRYRdSAMQ+S9x2QywVrLmAXMZ4xxaJqGyrJEVVW/A3IQQqBpGmqaBm3bUpZlvwNBEJCuaxhN01Df99T3Pc1m8zsQhiExZowoilDXdW8gDEMKwxB5ntNqtaI4jn8H5CCKIorjmJIkoSRJaLvd/g7IgbWW0jSlNE0pyzJar9fUtq0CfHnLoixLWi6XNJ/PNeALRO4FFdZ1PZOYEEYAAAAASUVORK5CYII='
  );

  tray = new Tray(icon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show JARVIS',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.center();
        }
      },
    },
    {
      label: 'Start Listening',
      click: () => {
        if (jarvisEngine) {
          jarvisEngine.start();
        }
      },
    },
    {
      label: 'Stop Listening',
      click: () => {
        if (jarvisEngine) {
          jarvisEngine.stop();
        }
      },
    },
    { type: 'separator' },
    {
      label: 'Trigger Wake Word (Test)',
      click: () => {
        if (jarvisEngine) {
          jarvisEngine.triggerWakeWord();
        }
      },
    },
    { type: 'separator' },
    {
      label: isSystemMuted ? 'Unmute System Audio' : 'Mute System Audio',
      click: () => {
        toggleSystemMute();
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.quit();
      },
    },
  ]);

  tray.setToolTip('JARVIS Voice Agent');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.center();
      }
    }
  });
}

// ==================== Audio Mute Functions ====================

async function getSystemVolume(): Promise<number> {
  try {
    const { stdout } = await execAsync(
      'powershell.exe -NoProfile -Command "(Get-AudioDevice -PlaybackVolume).Volume"'
    );
    return parseInt(stdout.trim(), 10) || 50;
  } catch (error) {
    logger.warn('Failed to get system volume, using default');
    return 50;
  }
}

async function setSystemMute(mute: boolean): Promise<void> {
  try {
    if (mute) {
      // Store current volume before muting
      previousVolume = await getSystemVolume();
      // Mute using nircmd (more reliable) or PowerShell fallback
      await execAsync('powershell.exe -NoProfile -Command "$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]173)"');
    } else {
      // Unmute
      await execAsync('powershell.exe -NoProfile -Command "$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]173)"');
    }

    isSystemMuted = mute;
    logger.info('System mute toggled', { muted: isSystemMuted });

    // Notify renderer
    if (mainWindow) {
      mainWindow.webContents.send('audio:mute-changed', isSystemMuted);
    }

    // Update tray menu
    createTray();
  } catch (error) {
    logger.error('Failed to set system mute', { error });
  }
}

async function toggleSystemMute(): Promise<boolean> {
  await setSystemMute(!isSystemMuted);
  return isSystemMuted;
}

// ==================== Initialize JARVIS ====================

function initializeJarvis() {
  jarvisEngine = new JarvisEngine();

  // Forward JARVIS events to renderer
  jarvisEngine.on('status', (state) => {
    if (mainWindow) {
      mainWindow.webContents.send('agent:status-changed', state);
    }
  });

  jarvisEngine.on('transcript', (message) => {
    if (mainWindow) {
      mainWindow.webContents.send('agent:message', message);
    }
  });

  jarvisEngine.on('metrics', (metrics) => {
    if (mainWindow) {
      mainWindow.webContents.send('cost:updated', metrics);
    }
  });

  jarvisEngine.on('error', (error) => {
    logger.error('JARVIS error', { error });
    if (mainWindow) {
      mainWindow.webContents.send('agent:error', { message: error.message });
    }
  });

  // Audio playback events for visualization
  jarvisEngine.on('audio:playing', () => {
    if (mainWindow) {
      mainWindow.webContents.send('audio:playing', { intensity: 0.7 });
    }
  });

  jarvisEngine.on('audio:stopped', () => {
    if (mainWindow) {
      mainWindow.webContents.send('audio:stopped');
    }
  });

  // Wake word detected - auto-mute if enabled
  jarvisEngine.on('wakeword', async () => {
    if (autoMuteEnabled && !isSystemMuted) {
      logger.info('Auto-muting system audio on wake word');
      await setSystemMute(true);
    }
  });

  // Interaction complete - auto-unmute if we auto-muted
  jarvisEngine.on('interaction:complete', async () => {
    if (autoMuteEnabled && isSystemMuted) {
      logger.info('Auto-unmuting system audio after interaction');
      await setSystemMute(false);
    }
  });

  // Only auto-start JARVIS if setup is already complete
  const hasCompletedSetup = settingsStore.get('hasCompletedSetup');
  const skipSettings = settingsStore.get('skipSettingsOnStartup');

  if (hasCompletedSetup && skipSettings) {
    isSetupComplete = true;
    // Load saved API keys into environment
    const savedApiKey = settingsStore.get('openaiApiKey');
    if (savedApiKey) {
      process.env.OPENAI_API_KEY = savedApiKey;
    }
    const savedElevenLabsKey = settingsStore.get('elevenLabsApiKey');
    if (savedElevenLabsKey) {
      process.env.ELEVENLABS_API_KEY = savedElevenLabsKey;
    }

    jarvisEngine.start().catch((error) => {
      logger.error('Failed to start JARVIS', { error });
    });
  }
}

// ==================== IPC Handlers ====================

function setupIPC() {
  ipcMain.handle('agent:start', async () => {
    // Check if we have required settings
    const apiKey = settingsStore.get('openaiApiKey');
    if (!apiKey) {
      logger.warn('Cannot start agent: No OpenAI API key configured');
      return { success: false, error: 'No API key' };
    }

    // Make sure env is set
    process.env.OPENAI_API_KEY = apiKey;

    if (jarvisEngine) {
      try {
        await jarvisEngine.start();
        return { success: true };
      } catch (error: any) {
        logger.error('Failed to start agent', { error: error.message });
        return { success: false, error: error.message };
      }
    }
    return { success: false, error: 'Engine not initialized' };
  });

  ipcMain.handle('agent:stop', async () => {
    if (jarvisEngine) {
      await jarvisEngine.stop();
    }
  });

  ipcMain.handle('agent:get-state', () => {
    return jarvisEngine?.getState() || null;
  });

  ipcMain.handle('agent:trigger-wakeword', () => {
    if (jarvisEngine) {
      jarvisEngine.triggerWakeWord();
    }
  });

  ipcMain.handle('config:get', () => {
    // Return config (you'd implement this)
    return {};
  });

  ipcMain.handle('cost:get-metrics', () => {
    // Return cost metrics
    return jarvisEngine?.getState().metrics || null;
  });

  // Audio mute handlers
  ipcMain.handle('audio:toggle-mute', async () => {
    return await toggleSystemMute();
  });

  ipcMain.handle('audio:get-mute-state', () => {
    return isSystemMuted;
  });

  ipcMain.handle('audio:set-mute', async (_event, mute: boolean) => {
    await setSystemMute(mute);
    return isSystemMuted;
  });

  ipcMain.handle('audio:set-auto-mute', (_event, enabled: boolean) => {
    autoMuteEnabled = enabled;
    logger.info('Auto-mute setting changed', { enabled });
    return autoMuteEnabled;
  });

  ipcMain.handle('audio:get-auto-mute', () => {
    return autoMuteEnabled;
  });

  // ==================== Settings Handlers ====================

  ipcMain.handle('settings:check-first-run', () => {
    const hasCompletedSetup = settingsStore.get('hasCompletedSetup');
    const skipSettings = settingsStore.get('skipSettingsOnStartup');

    return {
      isFirstRun: !hasCompletedSetup,
      showSettings: !hasCompletedSetup || !skipSettings,
    };
  });

  ipcMain.handle('settings:get', () => {
    return {
      openaiApiKey: settingsStore.get('openaiApiKey'),
      elevenLabsApiKey: settingsStore.get('elevenLabsApiKey'),
      elevenLabsVoiceId: settingsStore.get('elevenLabsVoiceId'),
      wakeWord: settingsStore.get('wakeWord'),
      sensitivity: settingsStore.get('sensitivity'),
      dailyBudget: settingsStore.get('dailyBudget'),
      monthlyBudget: settingsStore.get('monthlyBudget'),
      skipSettingsOnStartup: settingsStore.get('skipSettingsOnStartup'),
      runOnStartup: settingsStore.get('runOnStartup'),
    };
  });

  ipcMain.handle('settings:save', async (_event, settings: Partial<UserSettings>) => {
    // Save all settings
    Object.entries(settings).forEach(([key, value]) => {
      settingsStore.set(key as keyof UserSettings, value);
    });

    // Mark setup as complete
    settingsStore.set('hasCompletedSetup', true);
    isSetupComplete = true;

    // Handle run-on-startup
    if (settings.runOnStartup !== undefined) {
      app.setLoginItemSettings({
        openAtLogin: settings.runOnStartup,
        path: app.getPath('exe'),
      });
    }

    // Update environment variables for the config manager
    if (settings.openaiApiKey) {
      process.env.OPENAI_API_KEY = settings.openaiApiKey;
    }
    if (settings.elevenLabsApiKey) {
      process.env.ELEVENLABS_API_KEY = settings.elevenLabsApiKey;
    }
    if (settings.elevenLabsVoiceId) {
      process.env.ELEVENLABS_VOICE_ID = settings.elevenLabsVoiceId;
    }
    if (settings.wakeWord) {
      process.env.WAKE_WORD = settings.wakeWord;
    }
    if (settings.sensitivity !== undefined) {
      process.env.WAKE_WORD_SENSITIVITY = settings.sensitivity.toString();
    }
    if (settings.dailyBudget !== undefined) {
      process.env.DAILY_BUDGET_USD = settings.dailyBudget.toString();
    }
    if (settings.monthlyBudget !== undefined) {
      process.env.MONTHLY_BUDGET_USD = settings.monthlyBudget.toString();
    }

    logger.info('Settings saved', { hasCompletedSetup: true });

    return true;
  });
}

// ==================== App Lifecycle ====================

app.whenReady().then(() => {
  createWindow();
  createTray();
  initializeJarvis();
  setupIPC();

  logger.info('JARVIS application started');
});

app.on('window-all-closed', () => {
  // Don't quit on window close - keep running in tray
});

app.on('before-quit', async () => {
  // Restore audio if muted
  if (isSystemMuted) {
    await setSystemMute(false);
  }

  if (jarvisEngine) {
    jarvisEngine.stop();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
