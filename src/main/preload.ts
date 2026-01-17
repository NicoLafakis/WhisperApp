/**
 * JARVIS Voice Agent - Preload Script
 * Secure bridge between main process and renderer
 * Exposes only necessary IPC methods via contextBridge
 */

import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

// Define the API exposed to the renderer
const electronAPI = {
  // Agent control
  startAgent: () => ipcRenderer.invoke('agent:start'),
  stopAgent: () => ipcRenderer.invoke('agent:stop'),
  getAgentState: () => ipcRenderer.invoke('agent:get-state'),
  triggerWakeWord: () => ipcRenderer.invoke('agent:trigger-wakeword'),

  // Settings
  checkFirstRun: () => ipcRenderer.invoke('settings:check-first-run'),
  getSettings: () => ipcRenderer.invoke('settings:get'),
  saveSettings: (settings: Record<string, unknown>) => ipcRenderer.invoke('settings:save', settings),

  // Config & Metrics
  getConfig: () => ipcRenderer.invoke('config:get'),
  getCostMetrics: () => ipcRenderer.invoke('cost:get-metrics'),

  // Event listeners - one-way from main to renderer
  onStatusChanged: (callback: (state: unknown) => void) => {
    const listener = (_event: IpcRendererEvent, state: unknown) => callback(state);
    ipcRenderer.on('agent:status-changed', listener);
    return () => ipcRenderer.removeListener('agent:status-changed', listener);
  },

  onMessage: (callback: (message: unknown) => void) => {
    const listener = (_event: IpcRendererEvent, message: unknown) => callback(message);
    ipcRenderer.on('agent:message', listener);
    return () => ipcRenderer.removeListener('agent:message', listener);
  },

  onCostUpdated: (callback: (metrics: unknown) => void) => {
    const listener = (_event: IpcRendererEvent, metrics: unknown) => callback(metrics);
    ipcRenderer.on('cost:updated', listener);
    return () => ipcRenderer.removeListener('cost:updated', listener);
  },

  onError: (callback: (error: { message: string }) => void) => {
    const listener = (_event: IpcRendererEvent, error: { message: string }) => callback(error);
    ipcRenderer.on('agent:error', listener);
    return () => ipcRenderer.removeListener('agent:error', listener);
  },

  onAudioPlaying: (callback: (data: { intensity: number }) => void) => {
    const listener = (_event: IpcRendererEvent, data: { intensity: number }) => callback(data);
    ipcRenderer.on('audio:playing', listener);
    return () => ipcRenderer.removeListener('audio:playing', listener);
  },

  onAudioStopped: (callback: () => void) => {
    const listener = () => callback();
    ipcRenderer.on('audio:stopped', listener);
    return () => ipcRenderer.removeListener('audio:stopped', listener);
  },

  // Remove all listeners (cleanup)
  removeAllListeners: () => {
    ipcRenderer.removeAllListeners('agent:status-changed');
    ipcRenderer.removeAllListeners('agent:message');
    ipcRenderer.removeAllListeners('cost:updated');
    ipcRenderer.removeAllListeners('agent:error');
    ipcRenderer.removeAllListeners('audio:playing');
    ipcRenderer.removeAllListeners('audio:stopped');
  },
};

// Expose the API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', electronAPI);

// Type declaration for renderer
export type ElectronAPI = typeof electronAPI;
