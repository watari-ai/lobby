/**
 * Lobby - Electron Main Process
 * 
 * Desktop application entry point for the AI VTuber software.
 * Provides native window management and system integration.
 */

import { app, BrowserWindow, ipcMain, shell } from 'electron';
import * as path from 'path';

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

let mainWindow: BrowserWindow | null = null;

function createWindow(): void {
  // Create the browser window.
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 600,
    title: 'Lobby - AI VTuber',
    icon: path.join(__dirname, '../public/icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    // Transparent background for avatar overlay mode
    transparent: false,
    frame: true,
    show: false, // Don't show until ready
  });

  // Show window when ready to prevent flash
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  // Load the app
  if (isDev) {
    // In development, load from Vite dev server
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // In production, load from built files
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// This method will be called when Electron has finished initialization
app.whenReady().then(() => {
  createWindow();

  // On macOS it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed, except on macOS.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers for renderer communication

// Get app version
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

// Get platform info
ipcMain.handle('get-platform', () => {
  return {
    platform: process.platform,
    arch: process.arch,
    version: process.getSystemVersion(),
  };
});

// Window controls
ipcMain.on('window-minimize', () => {
  mainWindow?.minimize();
});

ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});

ipcMain.on('window-close', () => {
  mainWindow?.close();
});

// Toggle always on top (for overlay mode)
ipcMain.on('window-set-always-on-top', (_, value: boolean) => {
  mainWindow?.setAlwaysOnTop(value);
});

// Set window opacity (for overlay mode)
ipcMain.on('window-set-opacity', (_, value: number) => {
  mainWindow?.setOpacity(Math.max(0.1, Math.min(1.0, value)));
});
