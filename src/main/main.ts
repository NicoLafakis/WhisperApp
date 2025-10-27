/**
 * JARVIS Voice Agent - Electron Main Process
 */

import { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage } from 'electron';
import * as path from 'path';
import { JarvisEngine } from './JarvisEngine';
import { logger } from '../shared/utils/logger';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let jarvisEngine: JarvisEngine | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 400,
    height: 600,
    show: false,
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

  // Load the app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('blur', () => {
    if (mainWindow) {
      mainWindow.hide();
    }
  });
}

function createTray() {
  // Create a simple tray icon (you'll need to add a proper icon file)
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAGNSURBVDiNpZM9S8NQFIafk/RDq1YXBwcHB0EQBEFwcBAEQRAERQcHQQcHQRAEQRAEQRAEQRAEQRAEQRAEQRAEQRAEQdBBEARBEATBX/A7GaQm0ULb2WF5z3vPy7k3F/7JGIaBYRgYhoFhGBiGQRAEBEFAEAS/xjRNTNPENE1M0yQIAsIwJAwDDMMgiiLiOCYMQ+I4JooigiD4MYZhYJomhmFgmiZBEBBFEVEUEQQBQRBgWRZxHBPHMVEUEcex3yuKIsIw/DH/BsIwJAxDoigijmOiKCKOY6IoIgxD4jgmiiLiOCaOY+I4JoqiH/NvII5j4jgmiiKiKCKKIqIoIgxDoigiCAKCICAIAoIgIAxDgiD4Mf8GgiAgCAKCICAIAoIgIAgCwjAkCAKCICAMQ4IgIAxDwjD8Mf8GwjAkDEOCICAMQ4IgIAgCgiAgDEOCICAIAqIoIooi4jgmiiJ+jGmaRFFEGIaEYUgYhoRhSBiGhGFIEAQEQUAURURRRBRFxHFMFEX8GNM0iaKIMAwJw5AwDAnDkDAM+Qvj/5j0A3wBpvJmPpRzAAAAAElFTkSuQmCC'
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

  // Auto-start JARVIS
  jarvisEngine.start().catch((error) => {
    logger.error('Failed to start JARVIS', { error });
  });
}

// IPC handlers
function setupIPC() {
  ipcMain.handle('agent:start', async () => {
    if (jarvisEngine) {
      await jarvisEngine.start();
    }
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
}

// App lifecycle
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

app.on('before-quit', () => {
  if (jarvisEngine) {
    jarvisEngine.stop();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
