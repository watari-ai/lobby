import React, { useState, useCallback, useRef, useEffect } from 'react';

const BACKEND_URL = 'http://localhost:8100';

interface ScriptLine {
  text: string;
  emotion: string;
  wait_after: number;
  gesture: string | null;
}

interface RecordingStatus {
  session_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress_current: number;
  progress_total: number;
  progress_message: string;
  output_path: string | null;
  error: string | null;
}

export function RecordingPanel() {
  const [scriptText, setScriptText] = useState('');
  const [parsedLines, setParsedLines] = useState<ScriptLine[] | null>(null);
  const [session, setSession] = useState<RecordingStatus | null>(null);
  const [ttsUrl, setTtsUrl] = useState(() => localStorage.getItem('lobby_tts_url') || 'http://localhost:8001');
  const [ttsVoice, setTtsVoice] = useState(() => localStorage.getItem('lobby_tts_voice') || 'lobby');
  const [ttsProvider, setTtsProvider] = useState(() => localStorage.getItem('lobby_tts_provider') || 'miotts');
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Save TTS settings
  useEffect(() => {
    localStorage.setItem('lobby_tts_url', ttsUrl);
    localStorage.setItem('lobby_tts_voice', ttsVoice);
    localStorage.setItem('lobby_tts_provider', ttsProvider);
  }, [ttsUrl, ttsVoice, ttsProvider]);

  // Poll recording status
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const parseScript = useCallback(async () => {
    if (!scriptText.trim()) return;
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/recording/parse-script?script_text=${encodeURIComponent(scriptText)}`);
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      const data = await res.json();
      setParsedLines(data.lines);
    } catch (e: any) {
      setError(e.message);
    }
  }, [scriptText]);

  const startRecording = useCallback(async () => {
    if (!scriptText.trim()) return;
    setError(null);
    setSession(null);

    // For recording, we need avatar parts. Use placeholder paths that the user should configure.
    const avatarBase = localStorage.getItem('lobby_avatar_base') || '';
    const mouthClosed = localStorage.getItem('lobby_avatar_mouth_closed') || '';

    if (!avatarBase || !mouthClosed) {
      setError('Avatar paths not configured. Set base image and mouth-closed image paths in Settings → Avatar.');
      return;
    }

    try {
      const body = {
        script_text: scriptText,
        tts: {
          provider: ttsProvider,
          base_url: ttsUrl,
          voice: ttsVoice,
        },
        avatar: {
          base: avatarBase,
          mouth_closed: mouthClosed,
          mouth_open_s: localStorage.getItem('lobby_avatar_mouth_open') || mouthClosed,
          mouth_open_m: localStorage.getItem('lobby_avatar_mouth_open') || mouthClosed,
          mouth_open_l: localStorage.getItem('lobby_avatar_mouth_open') || mouthClosed,
        },
        video: { fps: 30, width: 1920, height: 1080, crf: 23 },
        output_dir: './output',
      };

      const res = await fetch(`${BACKEND_URL}/api/recording/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);

      const data: RecordingStatus = await res.json();
      setSession(data);

      // Start polling
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`${BACKEND_URL}/api/recording/status/${data.session_id}`);
          if (statusRes.ok) {
            const status: RecordingStatus = await statusRes.json();
            setSession(status);
            if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
              if (pollRef.current) clearInterval(pollRef.current);
              pollRef.current = null;
            }
          }
        } catch { /* ignore poll errors */ }
      }, 1000);
    } catch (e: any) {
      setError(e.message);
    }
  }, [scriptText, ttsUrl, ttsVoice, ttsProvider]);

  const cancelRecording = useCallback(async () => {
    if (!session) return;
    try {
      await fetch(`${BACKEND_URL}/api/recording/cancel/${session.session_id}`, { method: 'POST' });
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
      setSession((s) => s ? { ...s, status: 'cancelled' } : null);
    } catch { /* ignore */ }
  }, [session]);

  const isRecording = session?.status === 'pending' || session?.status === 'running';
  const progress = session && session.progress_total > 0
    ? Math.round((session.progress_current / session.progress_total) * 100)
    : 0;

  return (
    <div className="p-4 space-y-4">
      {/* Script Input */}
      <div>
        <label className="text-xs text-muted-foreground block mb-1">Script</label>
        <textarea
          value={scriptText}
          onChange={(e) => setScriptText(e.target.value)}
          placeholder={`おはロビィ！僕、倉土ロビィっす！\n[excited] マジでびっくりしたっす！\n[sad] ちょっと寂しかったっすね...`}
          className="w-full h-32 px-3 py-2 bg-secondary rounded-md text-sm text-foreground resize-y font-mono"
          disabled={isRecording}
        />
        <div className="flex gap-2 mt-1">
          <button
            onClick={parseScript}
            disabled={!scriptText.trim() || isRecording}
            className="px-3 py-1 text-xs bg-secondary hover:bg-accent rounded transition-colors disabled:opacity-50"
          >
            Preview
          </button>
          <span className="text-xs text-muted-foreground self-center">
            {scriptText.trim().split('\n').filter(Boolean).length} lines
          </span>
        </div>
      </div>

      {/* Parsed Preview */}
      {parsedLines && (
        <div className="bg-secondary/50 rounded-md p-3 max-h-40 overflow-y-auto">
          <div className="text-xs text-muted-foreground mb-1">Preview ({parsedLines.length} lines)</div>
          {parsedLines.map((line, i) => (
            <div key={i} className="text-xs py-0.5 flex gap-2">
              <span className="text-muted-foreground shrink-0">{i + 1}.</span>
              <span className={`shrink-0 px-1 rounded ${
                line.emotion === 'neutral' ? 'bg-gray-600' :
                line.emotion === 'happy' ? 'bg-yellow-600' :
                line.emotion === 'sad' ? 'bg-blue-600' :
                line.emotion === 'excited' ? 'bg-orange-600' :
                line.emotion === 'angry' ? 'bg-red-600' :
                line.emotion === 'surprised' ? 'bg-purple-600' : 'bg-gray-600'
              }`}>{line.emotion}</span>
              <span className="truncate">{line.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* TTS Settings */}
      <div className="space-y-2">
        <div className="text-xs text-muted-foreground">TTS Settings</div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-muted-foreground">Provider</label>
            <select
              value={ttsProvider}
              onChange={(e) => setTtsProvider(e.target.value)}
              className="w-full px-2 py-1 bg-secondary rounded text-xs"
              disabled={isRecording}
            >
              <option value="miotts">MioTTS</option>
              <option value="qwen3-tts">Qwen3-TTS</option>
              <option value="openai">OpenAI Compatible</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground">Voice</label>
            <input
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
              className="w-full px-2 py-1 bg-secondary rounded text-xs"
              disabled={isRecording}
            />
          </div>
        </div>
        <div>
          <label className="text-[10px] text-muted-foreground">TTS URL</label>
          <input
            value={ttsUrl}
            onChange={(e) => setTtsUrl(e.target.value)}
            className="w-full px-2 py-1 bg-secondary rounded text-xs"
            disabled={isRecording}
          />
        </div>
      </div>

      {/* Record Button */}
      <div className="flex gap-2">
        {!isRecording ? (
          <button
            onClick={startRecording}
            disabled={!scriptText.trim()}
            className="flex-1 py-2 bg-red-600 hover:bg-red-500 rounded-md text-sm font-medium transition-colors disabled:opacity-50"
          >
            🔴 Start Recording
          </button>
        ) : (
          <button
            onClick={cancelRecording}
            className="flex-1 py-2 bg-gray-600 hover:bg-gray-500 rounded-md text-sm font-medium transition-colors"
          >
            ⏹ Cancel
          </button>
        )}
      </div>

      {/* Progress */}
      {session && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className={`capitalize ${
              session.status === 'completed' ? 'text-green-400' :
              session.status === 'failed' ? 'text-red-400' :
              session.status === 'running' ? 'text-yellow-400' :
              session.status === 'cancelled' ? 'text-gray-400' :
              'text-muted-foreground'
            }`}>
              {session.status === 'completed' ? '✅ ' : session.status === 'failed' ? '❌ ' : ''}
              {session.status}
            </span>
            {session.progress_total > 0 && (
              <span className="text-muted-foreground">
                {session.progress_current}/{session.progress_total}
              </span>
            )}
          </div>

          {isRecording && (
            <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}

          {session.progress_message && (
            <p className="text-[10px] text-muted-foreground">{session.progress_message}</p>
          )}

          {session.output_path && (
            <div className="bg-green-900/30 border border-green-700/50 rounded p-2">
              <p className="text-xs text-green-300">Output:</p>
              <p className="text-[10px] text-green-400 font-mono break-all">{session.output_path}</p>
            </div>
          )}

          {session.error && (
            <div className="bg-red-900/30 border border-red-700/50 rounded p-2">
              <p className="text-xs text-red-400">{session.error}</p>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && !session?.error && (
        <div className="bg-red-900/30 border border-red-700/50 rounded p-2">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}
    </div>
  );
}
