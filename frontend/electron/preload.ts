/**
 * Lobby - Electron Preload Script
 * 
 * Securely exposes Electron APIs to the renderer process.
 * Uses contextBridge for safe IPC communication.
 */

import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods that allow the renderer process to use
// ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  getVersion: () => ipcRenderer.invoke('get-app-version'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  
  // Overlay mode
  setAlwaysOnTop: (value: boolean) => ipcRenderer.send('window-set-always-on-top', value),
  setOpacity: (value: number) => ipcRenderer.send('window-set-opacity', value),
  
  // Auto-updater
  updater: {
    check: () => ipcRenderer.invoke('updater-check'),
    download: () => ipcRenderer.invoke('updater-download'),
    install: () => ipcRenderer.send('updater-install'),
    onStatus: (callback: (status: UpdaterStatus) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, status: UpdaterStatus) => callback(status);
      ipcRenderer.on('updater-status', handler);
      return () => ipcRenderer.removeListener('updater-status', handler);
    },
  },
});

// TypeScript declaration for the exposed API
export interface UpdaterStatus {
  status: 'checking' | 'available' | 'not-available' | 'downloading' | 'downloaded' | 'error';
  version?: string;
  releaseDate?: string;
  releaseNotes?: string | { [key: string]: string };
  progress?: {
    percent: number;
    bytesPerSecond: number;
    transferred: number;
    total: number;
  };
  message?: string;
}

declare global {
  interface Window {
    electronAPI: {
      getVersion: () => Promise<string>;
      getPlatform: () => Promise<{
        platform: string;
        arch: string;
        version: string;
      }>;
      minimize: () => void;
      maximize: () => void;
      close: () => void;
      setAlwaysOnTop: (value: boolean) => void;
      setOpacity: (value: number) => void;
      updater: {
        check: () => Promise<{ success: boolean; version?: string; error?: string }>;
        download: () => Promise<{ success: boolean; error?: string }>;
        install: () => void;
        onStatus: (callback: (status: UpdaterStatus) => void) => () => void;
      };
    };
  }
}
