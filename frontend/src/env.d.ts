/// <reference types="vite/client" />

interface UpdaterAPI {
  onStatus: (callback: (status: any) => void) => () => void;
  download: () => Promise<void>;
  install: () => void;
}

interface ElectronAPI {
  updater?: UpdaterAPI;
  selectModelDirectory?: () => Promise<{
    canceled?: boolean;
    success?: boolean;
    modelPath?: string;
    error?: string;
  }>;
}

interface Window {
  electronAPI?: ElectronAPI;
}
