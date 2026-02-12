/**
 * SubtitleDisplay - リアルタイム字幕表示コンポーネント
 *
 * WebSocket経由で字幕を受信して表示する。
 * 感情に応じたスタイル変更、フェードイン/アウトアニメーション対応。
 */

import { useEffect, useState, useRef, useCallback } from 'react';

// 字幕データ型
interface Subtitle {
  id: string;
  text: string;
  speaker: string;
  style: 'normal' | 'excited' | 'sad' | 'angry' | 'whisper' | 'shout';
  emotion: string;
  duration_ms: number;
}

// スタイル定義
const subtitleStyles: Record<string, React.CSSProperties> = {
  normal: {
    color: '#ffffff',
    fontSize: '1.5rem',
    textShadow: '2px 2px 4px rgba(0, 0, 0, 0.8)',
  },
  excited: {
    color: '#ffeb3b',
    fontSize: '1.8rem',
    fontWeight: 'bold',
    textShadow: '2px 2px 4px rgba(255, 152, 0, 0.5)',
  },
  sad: {
    color: '#90caf9',
    fontSize: '1.4rem',
    opacity: 0.9,
    textShadow: '2px 2px 4px rgba(0, 0, 0, 0.6)',
  },
  angry: {
    color: '#ff5252',
    fontSize: '1.7rem',
    fontWeight: 'bold',
    textShadow: '2px 2px 4px rgba(183, 28, 28, 0.6)',
  },
  whisper: {
    color: '#e0e0e0',
    fontSize: '1.2rem',
    fontStyle: 'italic',
    opacity: 0.8,
    textShadow: '1px 1px 2px rgba(0, 0, 0, 0.4)',
  },
  shout: {
    color: '#ffffff',
    fontSize: '2rem',
    fontWeight: 'bold',
    textTransform: 'uppercase' as const,
    textShadow: '3px 3px 6px rgba(0, 0, 0, 0.9)',
  },
};

interface SubtitleDisplayProps {
  /** WebSocket URL (デフォルト: ws://localhost:8000/ws/subtitle) */
  wsUrl?: string;
  /** 表示位置 */
  position?: 'top' | 'center' | 'bottom';
  /** 背景の透明度 (0-1) */
  backgroundOpacity?: number;
  /** フォントファミリー */
  fontFamily?: string;
  /** 最大幅 (px) */
  maxWidth?: number;
  /** カスタムスタイル */
  style?: React.CSSProperties;
}

export function SubtitleDisplay({
  wsUrl = 'ws://localhost:8000/ws/subtitle',
  position = 'bottom',
  backgroundOpacity = 0.6,
  fontFamily = '"Noto Sans JP", "Hiragino Sans", sans-serif',
  maxWidth = 800,
  style,
}: SubtitleDisplayProps) {
  const [subtitle, setSubtitle] = useState<Subtitle | null>(null);
  const [visible, setVisible] = useState(false);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // WebSocket接続
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    console.log('[Subtitle] Connecting to', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[Subtitle] Connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'subtitle') {
          if (data.action === 'show' && data.data) {
            setSubtitle(data.data);
            setVisible(true);
          } else if (data.action === 'clear') {
            setVisible(false);
            // フェードアウト後にクリア
            setTimeout(() => setSubtitle(null), 200);
          }
        }
      } catch (err) {
        console.error('[Subtitle] Parse error:', err);
      }
    };

    ws.onclose = () => {
      console.log('[Subtitle] Disconnected');
      setConnected(false);
      // 再接続
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error('[Subtitle] WebSocket error:', err);
    };

    wsRef.current = ws;
  }, [wsUrl]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  // 位置スタイル
  const positionStyle: React.CSSProperties = {
    top: position === 'top' ? '10%' : position === 'center' ? '50%' : undefined,
    bottom: position === 'bottom' ? '15%' : undefined,
    transform: position === 'center' ? 'translateX(-50%) translateY(-50%)' : 'translateX(-50%)',
  };

  // 現在の字幕スタイル
  const currentStyle = subtitle
    ? subtitleStyles[subtitle.style] || subtitleStyles.normal
    : subtitleStyles.normal;

  return (
    <div
      style={{
        position: 'absolute',
        left: '50%',
        ...positionStyle,
        zIndex: 1000,
        pointerEvents: 'none',
        transition: 'opacity 0.2s ease-in-out',
        opacity: visible ? 1 : 0,
        ...style,
      }}
    >
      {subtitle && (
        <div
          style={{
            backgroundColor: `rgba(0, 0, 0, ${backgroundOpacity})`,
            padding: '12px 24px',
            borderRadius: '8px',
            maxWidth: `${maxWidth}px`,
            textAlign: 'center',
            fontFamily,
            ...currentStyle,
          }}
        >
          {/* 話者名 */}
          {subtitle.speaker && (
            <div
              style={{
                fontSize: '0.8em',
                marginBottom: '4px',
                color: '#a0a0a0',
              }}
            >
              {subtitle.speaker}
            </div>
          )}

          {/* 字幕テキスト */}
          <div
            style={{
              whiteSpace: 'pre-wrap',
              lineHeight: 1.4,
            }}
          >
            {subtitle.text}
          </div>
        </div>
      )}

      {/* 接続状態インジケーター（デバッグ用、本番では非表示） */}
      {import.meta.env.DEV && (
        <div
          style={{
            position: 'fixed',
            bottom: '5px',
            right: '5px',
            fontSize: '10px',
            color: connected ? '#4caf50' : '#f44336',
            pointerEvents: 'none',
          }}
        >
          {connected ? '● Subtitle WS' : '○ Disconnected'}
        </div>
      )}
    </div>
  );
}

export default SubtitleDisplay;
