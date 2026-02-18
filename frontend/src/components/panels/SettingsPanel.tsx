import React, { useState, useRef, useCallback } from 'react';
import { useBackend } from '../../contexts/BackendContext';
import { useLobbyStore } from '../../stores/lobbyStore';
import type { Expression } from '../../types';
import {
  findModelFileInFileList,
  findModelFromDrop,
} from '../../lib/localModel';

const BACKEND_URL = 'http://localhost:8100';

/**
 * Upload local files to backend temp dir and return an HTTP model URL.
 * Files are sent with their relative paths as filenames so the backend
 * recreates the directory structure.
 */
async function uploadModelFiles(allFiles: Map<string, File>): Promise<string> {
  const formData = new FormData();
  for (const [relativePath, file] of allFiles) {
    // Use relative path as filename so backend preserves structure
    formData.append('files', file, relativePath);
  }
  const res = await fetch(`${BACKEND_URL}/api/models/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Upload failed');
  }
  const data = await res.json();
  return `${BACKEND_URL}${data.modelUrl}`;
}

/**
 * Mount a local directory path via backend and return an HTTP model URL.
 */
async function mountModelDir(dirPath: string): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/api/models/mount`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: dirPath }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Mount failed');
  }
  const data = await res.json();
  return `${BACKEND_URL}${data.modelUrl}`;
}

const EXPRESSIONS: Expression[] = [
  'neutral',
  'happy',
  'sad',
  'angry',
  'surprised',
  'thinking',
];

const EXPRESSION_EMOJI: Record<Expression, string> = {
  neutral: '😐',
  happy: '😊',
  sad: '😢',
  excited: '🤩',
  angry: '😠',
  surprised: '😲',
  thinking: '🤔',
};

export function SettingsPanel() {
  const { connected, reconnect, reconnectAttempts, setExpression, analyzeText, speak } = useBackend();
  const { expression, modelPath, setModelPath, gatewayUrl, setGatewayUrl, gatewayApiKey, setGatewayApiKey } = useLobbyStore();
  const [testText, setTestText] = useState('');
  const [speakText, setSpeakText] = useState('おはロビィ！僕、倉土ロビィっす！');
  const [audioPath, setAudioPath] = useState('');
  const [modelPathInput, setModelPathInput] = useState(modelPath);
  const [localDirPath, setLocalDirPath] = useState('');
  const [gatewayUrlInput, setGatewayUrlInput] = useState(gatewayUrl);
  const [gatewayApiKeyInput, setGatewayApiKeyInput] = useState(gatewayApiKey);
  const [showApiKey, setShowApiKey] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const DEFAULT_MODEL_URL = 'https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display/test/assets/haru/haru_greeter_t03.model3.json';
  const isElectron = typeof window !== 'undefined' && !!(window as any).electronAPI?.selectModelDirectory;

  const handleAnalyzeText = () => {
    if (testText.trim()) {
      analyzeText(testText);
    }
  };

  const handleSpeak = () => {
    if (speakText.trim() && audioPath.trim()) {
      speak(speakText, audioPath);
    }
  };

  // Directory picker (Electron or browser fallback)
  const handleSelectDirectory = useCallback(async () => {
    setModelError(null);
    if (isElectron) {
      setModelLoading(true);
      try {
        const result = await (window as any).electronAPI.selectModelDirectory();
        if (result.canceled) { setModelLoading(false); return; }
        if (!result.success) { setModelError(result.error || 'Failed'); setModelLoading(false); return; }
        // Mount the directory via backend API — gives us proper HTTP URLs
        // that pixi-live2d-display can resolve relative paths against
        const dirPath = result.modelPath.substring(0, result.modelPath.lastIndexOf('/'));
        const httpUrl = await mountModelDir(dirPath);
        setModelPathInput(httpUrl);
        setModelPath(httpUrl);
      } catch (err: any) {
        setModelError(err.message);
      } finally {
        setModelLoading(false);
      }
    } else {
      // Browser: trigger webkitdirectory input
      fileInputRef.current?.click();
    }
  }, [isElectron, setModelPath]);

  // Browser file input handler (webkitdirectory)
  const handleFileInputChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setModelError(null);
    setModelLoading(true);
    try {
      const modelFile = findModelFileInFileList(files);
      if (!modelFile) { setModelError('No .model3.json found in directory'); setModelLoading(false); return; }
      // Build allFiles map with relative paths from webkitRelativePath
      const allFiles = new Map<string, File>();
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        allFiles.set(f.webkitRelativePath || f.name, f);
      }
      // Upload to backend and get HTTP URL (avoids blob: URL issues)
      const httpUrl = await uploadModelFiles(allFiles);
      setModelPathInput(httpUrl);
      setModelPath(httpUrl);
    } catch (err: any) {
      setModelError(err.message);
    } finally {
      setModelLoading(false);
      // Reset input so same directory can be re-selected
      e.target.value = '';
    }
  }, [setModelPath]);

  // Drag & Drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    setModelError(null);
    setModelLoading(true);
    try {
      const result = await findModelFromDrop(e.dataTransfer);
      if (!result) { setModelError('No .model3.json found in dropped items'); setModelLoading(false); return; }
      // Upload to backend and get HTTP URL (avoids blob: URL issues)
      const httpUrl = await uploadModelFiles(result.allFiles);
      setModelPathInput(httpUrl);
      setModelPath(httpUrl);
    } catch (err: any) {
      setModelError(err.message);
    } finally {
      setModelLoading(false);
    }
  }, [setModelPath]);

  return (
    <div className="p-4 space-y-6">
      {/* Connection Status */}
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          WebSocket Connection
        </h3>
        <div className="text-sm text-muted-foreground">
          <p>Status: {connected ? 'Connected' : `Disconnected${reconnectAttempts > 0 ? ` (retry ${reconnectAttempts}/10)` : ''}`}</p>
          <p>URL: ws://localhost:8100/ws/live2d</p>
        </div>
        {!connected && (
          <button
            onClick={reconnect}
            className="px-3 py-1.5 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 transition-colors"
          >
            Reconnect
          </button>
        )}
      </section>

      {/* Expression Control */}
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Expression Control</h3>
        <p className="text-xs text-muted-foreground">Current: {EXPRESSION_EMOJI[expression]} {expression}</p>
        <div className="grid grid-cols-3 gap-2">
          {EXPRESSIONS.map((expr) => (
            <button
              key={expr}
              onClick={() => setExpression(expr)}
              disabled={!connected}
              className={`px-3 py-2 rounded text-sm transition-colors flex items-center justify-center gap-1 ${
                expression === expr
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-accent disabled:opacity-50'
              }`}
            >
              <span>{EXPRESSION_EMOJI[expr]}</span>
              <span className="capitalize">{expr}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Text Analysis Test */}
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Emotion Analysis Test</h3>
        <p className="text-xs text-muted-foreground">
          Enter text to analyze emotion and update expression
        </p>
        <textarea
          value={testText}
          onChange={(e) => setTestText(e.target.value)}
          placeholder="マジっすか！やばいっすね！"
          className="w-full h-20 px-3 py-2 bg-secondary text-foreground rounded text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          onClick={handleAnalyzeText}
          disabled={!connected || !testText.trim()}
          className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          Analyze Emotion
        </button>
      </section>

      {/* Speech Test */}
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Speech Test (with Lipsync)</h3>
        <p className="text-xs text-muted-foreground">
          Combine text emotion + audio for lipsync
        </p>
        <textarea
          value={speakText}
          onChange={(e) => setSpeakText(e.target.value)}
          placeholder="台詞テキスト"
          className="w-full h-16 px-3 py-2 bg-secondary text-foreground rounded text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <input
          type="text"
          value={audioPath}
          onChange={(e) => setAudioPath(e.target.value)}
          placeholder="/path/to/audio.mp3"
          className="w-full px-3 py-2 bg-secondary text-foreground rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          onClick={handleSpeak}
          disabled={!connected || !speakText.trim() || !audioPath.trim()}
          className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          Start Speaking
        </button>
      </section>

      {/* Live2D Model */}
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Live2D Model</h3>
        <p className="text-xs text-muted-foreground">
          URL, local path, or drag &amp; drop a model directory.
        </p>

        {/* URL Input */}
        <input
          type="text"
          value={modelPathInput}
          onChange={(e) => setModelPathInput(e.target.value)}
          placeholder={DEFAULT_MODEL_URL}
          className="w-full px-3 py-2 bg-secondary text-foreground rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => setModelPath(modelPathInput)}
            disabled={modelLoading}
            className="flex-1 px-3 py-2 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            Apply URL
          </button>
          <button
            onClick={handleSelectDirectory}
            disabled={modelLoading}
            className="flex-1 px-3 py-2 bg-secondary text-secondary-foreground rounded text-sm hover:bg-accent transition-colors disabled:opacity-50"
          >
            {modelLoading ? '...' : '📁 Browse'}
          </button>
        </div>

        {/* Local Path Mount (via backend) */}
        <div className="flex gap-2">
          <input
            type="text"
            value={localDirPath}
            onChange={(e) => setLocalDirPath(e.target.value)}
            placeholder="/Users/w/ren_pro_jp/runtime"
            className="flex-1 px-3 py-2 bg-secondary text-foreground rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            onClick={async () => {
              if (!localDirPath.trim()) return;
              setModelError(null);
              setModelLoading(true);
              try {
                const httpUrl = await mountModelDir(localDirPath.trim());
                setModelPathInput(httpUrl);
                setModelPath(httpUrl);
              } catch (err: any) {
                setModelError(err.message);
              } finally {
                setModelLoading(false);
              }
            }}
            disabled={modelLoading || !localDirPath.trim()}
            className="px-3 py-2 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {modelLoading ? '...' : 'Load'}
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          Or enter a local directory path and click Load (served via backend)
        </p>

        {/* Hidden file input for browser fallback */}
        <input
          ref={fileInputRef}
          type="file"
          // @ts-expect-error webkitdirectory is non-standard
          webkitdirectory=""
          className="hidden"
          onChange={handleFileInputChange}
        />

        {/* Drag & Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors cursor-pointer ${
            isDragOver
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border text-muted-foreground hover:border-primary/50'
          }`}
          onClick={handleSelectDirectory}
        >
          <div className="text-2xl mb-1">{isDragOver ? '📥' : '🎭'}</div>
          <p className="text-xs">
            {isDragOver
              ? 'Drop model here'
              : 'Drag & drop .model3.json or model folder'}
          </p>
        </div>

        {/* Reset to default */}
        {modelPath && (
          <button
            onClick={() => { setModelPath(''); setModelPathInput(''); }}
            className="w-full px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            ↩ Reset to default model
          </button>
        )}

        {/* Error display */}
        {modelError && (
          <p className="text-xs text-red-400">⚠️ {modelError}</p>
        )}

        <p className="text-xs text-muted-foreground break-all">
          Default: {DEFAULT_MODEL_URL}
        </p>
      </section>

      {/* Gateway URL & API Key */}
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Gateway Settings</h3>
        <p className="text-xs text-muted-foreground">
          OpenClaw Gateway URL and API Key for external integrations.
        </p>
        <input
          type="text"
          value={gatewayUrlInput}
          onChange={(e) => setGatewayUrlInput(e.target.value)}
          placeholder="https://gateway.example.com"
          className="w-full px-3 py-2 bg-secondary text-foreground rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <div className="relative">
          <input
            type={showApiKey ? 'text' : 'password'}
            value={gatewayApiKeyInput}
            onChange={(e) => setGatewayApiKeyInput(e.target.value)}
            placeholder="API Key"
            className="w-full px-3 py-2 pr-10 bg-secondary text-foreground rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            type="button"
            onClick={() => setShowApiKey((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-sm"
            title={showApiKey ? 'Hide' : 'Show'}
          >
            {showApiKey ? '🙈' : '👁'}
          </button>
        </div>
        <button
          onClick={() => { setGatewayUrl(gatewayUrlInput); setGatewayApiKey(gatewayApiKeyInput); }}
          className="w-full px-3 py-2 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 transition-colors"
        >
          Save
        </button>
      </section>

      {/* Version Info */}
      <section className="pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground">
          Lobby v0.8.0 • Web UI • Phase 6
        </p>
      </section>
    </div>
  );
}
