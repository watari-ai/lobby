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
});

// TypeScript declaration for the exposed API
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
    };
  }
}
