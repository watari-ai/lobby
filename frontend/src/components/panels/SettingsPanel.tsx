import React, { useState } from 'react';
import { useBackend } from '../../contexts/BackendContext';
import { useLobbyStore } from '../../stores/lobbyStore';
import type { Expression } from '../../types';

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
  angry: '😠',
  surprised: '😲',
  thinking: '🤔',
};

export function SettingsPanel() {
  const { connected, reconnect, reconnectAttempts, setExpression, analyzeText, speak } = useBackend();
  const { expression } = useLobbyStore();
  const [testText, setTestText] = useState('');
  const [speakText, setSpeakText] = useState('おはロビィ！僕、倉土ロビィっす！');
  const [audioPath, setAudioPath] = useState('');

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
          <p>URL: ws://localhost:8000/ws/live2d</p>
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

      {/* Version Info */}
      <section className="pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground">
          Lobby v0.8.0 • Web UI • Phase 6
        </p>
      </section>
    </div>
  );
}
