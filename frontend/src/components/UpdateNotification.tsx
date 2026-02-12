/**
 * UpdateNotification - Auto-update notification component
 * 
 * Shows update availability, download progress, and install prompt.
 */

import { useEffect, useState } from 'react';
import { Download, RefreshCw, X, CheckCircle, AlertCircle } from 'lucide-react';

interface UpdaterStatus {
  status: 'checking' | 'available' | 'not-available' | 'downloading' | 'downloaded' | 'error';
  version?: string;
  releaseDate?: string;
  progress?: {
    percent: number;
    bytesPerSecond: number;
    transferred: number;
    total: number;
  };
  message?: string;
}

export function UpdateNotification() {
  const [status, setStatus] = useState<UpdaterStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Only run in Electron environment
    if (!window.electronAPI?.updater) return;

    const unsubscribe = window.electronAPI.updater.onStatus((newStatus) => {
      setStatus(newStatus);
      // Reset dismissed state when new update is available
      if (newStatus.status === 'available') {
        setDismissed(false);
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const handleDownload = async () => {
    if (!window.electronAPI?.updater) return;
    await window.electronAPI.updater.download();
  };

  const handleInstall = () => {
    if (!window.electronAPI?.updater) return;
    window.electronAPI.updater.install();
  };

  const handleDismiss = () => {
    setDismissed(true);
  };

  // Don't show if no status, dismissed, or no update
  if (!status || dismissed) return null;
  if (status.status === 'checking' || status.status === 'not-available') return null;

  // Format bytes
  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Format speed
  const formatSpeed = (bytesPerSecond: number) => {
    return `${formatBytes(bytesPerSecond)}/s`;
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-900">
        <div className="flex items-center gap-2">
          {status.status === 'error' ? (
            <AlertCircle className="w-5 h-5 text-red-400" />
          ) : status.status === 'downloaded' ? (
            <CheckCircle className="w-5 h-5 text-green-400" />
          ) : (
            <RefreshCw className={`w-5 h-5 text-blue-400 ${status.status === 'downloading' ? 'animate-spin' : ''}`} />
          )}
          <span className="font-medium text-white">
            {status.status === 'available' && 'Update Available'}
            {status.status === 'downloading' && 'Downloading...'}
            {status.status === 'downloaded' && 'Ready to Install'}
            {status.status === 'error' && 'Update Error'}
          </span>
        </div>
        <button
          onClick={handleDismiss}
          className="p-1 hover:bg-gray-700 rounded transition-colors"
        >
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {status.status === 'available' && (
          <>
            <p className="text-sm text-gray-300 mb-3">
              Version <span className="font-mono text-white">{status.version}</span> is available.
            </p>
            <button
              onClick={handleDownload}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
            >
              <Download className="w-4 h-4" />
              Download Update
            </button>
          </>
        )}

        {status.status === 'downloading' && status.progress && (
          <>
            <div className="mb-2">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>{formatBytes(status.progress.transferred)} / {formatBytes(status.progress.total)}</span>
                <span>{formatSpeed(status.progress.bytesPerSecond)}</span>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${status.progress.percent}%` }}
                />
              </div>
            </div>
            <p className="text-xs text-gray-400 text-center">
              {status.progress.percent.toFixed(0)}% complete
            </p>
          </>
        )}

        {status.status === 'downloaded' && (
          <>
            <p className="text-sm text-gray-300 mb-3">
              Version <span className="font-mono text-white">{status.version}</span> is ready.
              Restart to apply the update.
            </p>
            <button
              onClick={handleInstall}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Restart & Install
            </button>
          </>
        )}

        {status.status === 'error' && (
          <p className="text-sm text-red-400">
            {status.message || 'Failed to check for updates.'}
          </p>
        )}
      </div>
    </div>
  );
}
