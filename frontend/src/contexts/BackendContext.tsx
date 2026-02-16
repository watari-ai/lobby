/**
 * BackendContext - バックエンド同期のReactコンテキスト
 * 
 * 子コンポーネントからバックエンドとの通信機能にアクセスできます。
 */

import React, { createContext, useContext, type ReactNode } from 'react';
import { useBackendSync } from '../hooks/useBackendSync';
import type { Expression } from '../types';

interface BackendContextValue {
  /** WebSocket接続状態 */
  connected: boolean;
  /** 再接続試行回数 */
  reconnectAttempts: number;
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

const BackendContext = createContext<BackendContextValue | null>(null);

interface BackendProviderProps {
  children: ReactNode;
  /** WebSocket URL (default: ws://localhost:8100/ws/live2d) */
  url?: string;
}

export function BackendProvider({ children, url }: BackendProviderProps) {
  const backend = useBackendSync({
    url: url || 'ws://localhost:8100/ws/live2d',
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
  });

  return (
    <BackendContext.Provider value={backend}>
      {children}
    </BackendContext.Provider>
  );
}

export function useBackend(): BackendContextValue {
  const context = useContext(BackendContext);
  if (!context) {
    throw new Error('useBackend must be used within a BackendProvider');
  }
  return context;
}

export default BackendContext;
