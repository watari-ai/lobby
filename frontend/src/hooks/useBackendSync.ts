/**
 * useBackendSync - バックエンドとの双方向WebSocket同期フック
 * 
 * Zustandストアとバックエンドの状態をリアルタイムで同期します。
 */

import { useEffect, useRef, useCallback } from 'react';
import { useLobbyStore } from '../stores/lobbyStore';
import type { Expression, Live2DParams } from '../types';

// バックエンドからのメッセージタイプ
interface ParametersMessage {
  type: 'parameters';
  data: Live2DParams;
}

interface FrameMessage {
  type: 'frame';
  timestamp_ms: number;
  parameters: Live2DParams;
  expression?: string;
  motion?: string;
}

interface EmotionMessage {
  type: 'emotion';
  expression: Expression;
  text?: string;
  intensity?: number;
}

interface MotionMessage {
  type: 'motion';
  motion: string;
}

interface SpeakingMessage {
  type: 'speaking';
  status: 'started' | 'stopped';
  frame_count?: number;
  expression?: string;
}

interface StatusMessage {
  type: 'status';
  mode?: 'recording' | 'live' | 'dialogue' | 'idle';
  subtitle?: { text: string; language?: string };
  scene?: { background: string; camera: string };
}

interface ErrorMessage {
  type: 'error';
  message: string;
}

type BackendMessage =
  | ParametersMessage
  | FrameMessage
  | EmotionMessage
  | MotionMessage
  | SpeakingMessage
  | StatusMessage
  | ErrorMessage;

// フロントエンドからのアクションタイプ
export interface SetExpressionAction {
  action: 'set_expression';
  expression: Expression;
}

export interface SetParamAction {
  action: 'set_param';
  name: string;
  value: number;
}

export interface PlayMotionAction {
  action: 'play_motion';
  motion: string;
}

export interface AnalyzeTextAction {
  action: 'analyze_text';
  text: string;
}

export interface SpeakAction {
  action: 'speak';
  text: string;
  audio_path: string;
}

export interface StopAction {
  action: 'stop';
}

export interface SetCameraAction {
  action: 'set_camera';
  preset?: string;
  zoom?: number;
  offsetX?: number;
  offsetY?: number;
}

export interface SetBackgroundAction {
  action: 'set_background';
  type: 'color' | 'image' | 'video';
  source: string;
}

export interface SetSubtitleAction {
  action: 'set_subtitle';
  text?: string;
  enabled?: boolean;
  font?: Record<string, unknown>;
  position?: Record<string, unknown>;
}

export interface PlayBgmAction {
  action: 'play_bgm';
  track: string;
}

export interface StopBgmAction {
  action: 'stop_bgm';
}

export interface PlaySeAction {
  action: 'play_se';
  id: string;
}

export interface TriggerEffectAction {
  action: 'trigger_effect';
  type: string;
  intensity?: number;
}

type FrontendAction =
  | SetExpressionAction
  | SetParamAction
  | PlayMotionAction
  | AnalyzeTextAction
  | SpeakAction
  | StopAction
  | SetCameraAction
  | SetBackgroundAction
  | SetSubtitleAction
  | PlayBgmAction
  | StopBgmAction
  | PlaySeAction
  | TriggerEffectAction;

interface UseBackendSyncOptions {
  /** WebSocket URL (default: ws://localhost:8000/ws/live2d) */
  url?: string;
  /** 自動再接続の有効化 (default: true) */
  autoReconnect?: boolean;
  /** 再接続間隔 (ms) (default: 3000) */
  reconnectInterval?: number;
  /** 最大再接続試行回数 (default: 10) */
  maxReconnectAttempts?: number;
}

interface UseBackendSyncResult {
  /** WebSocket接続状態 */
  connected: boolean;
  /** 再接続試行回数 */
  reconnectAttempts: number;
  /** アクション送信 */
  sendAction: (action: FrontendAction) => void;
  /** 表情変更 */
  setExpression: (expression: Expression) => void;
  /** パラメータ変更 */
  setParam: (name: string, value: number) => void;
  /** モーション再生 */
  playMotion: (motion: string) => void;
  /** テキスト感情分析 */
  analyzeText: (text: string) => void;
  /** 音声付き発話 */
  speak: (text: string, audioPath: string) => void;
  /** ストリーミング停止 */
  stop: () => void;
  /** 手動再接続 */
  reconnect: () => void;
}

/**
 * バックエンドとの双方向WebSocket同期フック
 */
export function useBackendSync(
  options: UseBackendSyncOptions = {}
): UseBackendSyncResult {
  const {
    url = 'ws://localhost:8000/ws/live2d',
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);

  // Zustandストアの状態と更新関数
  const setConnected = useLobbyStore((state) => state.setConnected);
  const setLive2DParams = useLobbyStore((state) => state.setLive2DParams);
  const setExpression = useLobbyStore((state) => state.setExpression);
  const setSubtitleText = useLobbyStore((state) => state.setSubtitleText);
  const setBackgroundSource = useLobbyStore((state) => state.setBackgroundSource);
  const connected = useLobbyStore((state) => state.connected);

  // メッセージハンドラー
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const message: BackendMessage = JSON.parse(event.data);

        switch (message.type) {
          case 'parameters':
            // Live2Dパラメータ更新
            setLive2DParams(message.data);
            break;

          case 'frame':
            // フレーム更新（パラメータ＋表情）
            setLive2DParams(message.parameters);
            if (message.expression) {
              setExpression(message.expression as Expression);
            }
            break;

          case 'emotion':
            // 感情分析結果
            setExpression(message.expression);
            console.log(`[Emotion] ${message.expression} - "${message.text || ''}"`);
            break;

          case 'motion':
            // モーション通知（フロントエンドで再生処理）
            console.log(`[Motion] ${message.motion}`);
            // TODO: Live2Dモーション再生処理
            break;

          case 'speaking':
            // 発話状態
            console.log(`[Speaking] ${message.status}`);
            break;

          case 'status':
            // ステータス更新（字幕、シーン等）
            if (message.subtitle?.text) {
              setSubtitleText(message.subtitle.text);
            }
            if (message.scene?.background) {
              setBackgroundSource(message.scene.background);
            }
            break;

          case 'error':
            console.error(`[Backend Error] ${message.message}`);
            break;

          default:
            console.warn('[WebSocket] Unknown message type:', message);
        }
      } catch (e) {
        console.error('[WebSocket] Failed to parse message:', e);
      }
    },
    [setLive2DParams, setExpression, setSubtitleText, setBackgroundSource]
  );

  // WebSocket接続
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      console.log(`[WebSocket] Connecting to ${url}...`);
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setConnected(true);
        reconnectAttemptsRef.current = 0;

        // 初期状態を要求
        ws.send(JSON.stringify({ action: 'get_status' }));
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        console.log(`[WebSocket] Disconnected (code: ${event.code})`);
        setConnected(false);
        wsRef.current = null;

        // 自動再接続
        if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          console.log(
            `[WebSocket] Reconnecting in ${reconnectInterval}ms... ` +
            `(attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
          );
          reconnectTimeoutRef.current = window.setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('[WebSocket] Failed to connect:', e);
      setConnected(false);
    }
  }, [url, autoReconnect, reconnectInterval, maxReconnectAttempts, handleMessage, setConnected]);

  // アクション送信
  const sendAction = useCallback((action: FrontendAction) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(action));
    } else {
      console.warn('[WebSocket] Not connected, cannot send action:', action);
    }
  }, []);

  // 便利なアクション関数
  const setExpressionAction = useCallback(
    (expression: Expression) => sendAction({ action: 'set_expression', expression }),
    [sendAction]
  );

  const setParam = useCallback(
    (name: string, value: number) => sendAction({ action: 'set_param', name, value }),
    [sendAction]
  );

  const playMotion = useCallback(
    (motion: string) => sendAction({ action: 'play_motion', motion }),
    [sendAction]
  );

  const analyzeText = useCallback(
    (text: string) => sendAction({ action: 'analyze_text', text }),
    [sendAction]
  );

  const speak = useCallback(
    (text: string, audioPath: string) => sendAction({ action: 'speak', text, audio_path: audioPath }),
    [sendAction]
  );

  const stop = useCallback(() => sendAction({ action: 'stop' }), [sendAction]);

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    reconnectAttemptsRef.current = 0;
    if (wsRef.current) {
      wsRef.current.close();
    }
    connect();
  }, [connect]);

  // 初期接続とクリーンアップ
  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    connected,
    reconnectAttempts: reconnectAttemptsRef.current,
    sendAction,
    setExpression: setExpressionAction,
    setParam,
    playMotion,
    analyzeText,
    speak,
    stop,
    reconnect,
  };
}

export default useBackendSync;
