import { useState, useEffect, useCallback, useRef } from 'react';

interface Live2DParams {
  ParamMouthOpenY?: number;
  ParamMouthForm?: number;
  ParamEyeLOpen?: number;
  ParamEyeROpen?: number;
  ParamEyeBallX?: number;
  ParamEyeBallY?: number;
  ParamBrowLY?: number;
  ParamBrowRY?: number;
  ParamAngleX?: number;
  ParamAngleY?: number;
  ParamAngleZ?: number;
  ParamBreath?: number;
}

interface WebSocketMessage {
  type: 'parameters' | 'frame' | 'motion' | 'error';
  data?: Live2DParams;
  timestamp_ms?: number;
  parameters?: Live2DParams;
  expression?: string;
  motion?: string;
  message?: string;
}

interface UseLive2DWebSocketResult {
  connected: boolean;
  params: Live2DParams;
  expression: string;
  sendMessage: (message: object) => void;
}

const DEFAULT_PARAMS: Live2DParams = {
  ParamMouthOpenY: 0,
  ParamMouthForm: 0,
  ParamEyeLOpen: 1,
  ParamEyeROpen: 1,
  ParamEyeBallX: 0,
  ParamEyeBallY: 0,
  ParamBrowLY: 0,
  ParamBrowRY: 0,
  ParamAngleX: 0,
  ParamAngleY: 0,
  ParamAngleZ: 0,
  ParamBreath: 0,
};

export function useLive2DWebSocket(url: string): UseLive2DWebSocketResult {
  const [connected, setConnected] = useState(false);
  const [params, setParams] = useState<Live2DParams>(DEFAULT_PARAMS);
  const [expression, setExpression] = useState('neutral');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
          switch (message.type) {
            case 'parameters':
              if (message.data) {
                setParams(prev => ({ ...prev, ...message.data }));
              }
              break;
              
            case 'frame':
              if (message.parameters) {
                setParams(prev => ({ ...prev, ...message.parameters }));
              }
              if (message.expression) {
                setExpression(message.expression);
              }
              break;
              
            case 'error':
              console.error('WebSocket error:', message.message);
              break;
          }
        } catch (e) {
          console.error('Failed to parse message:', e);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        wsRef.current = null;

        // 自動再接続（3秒後）
        reconnectTimeoutRef.current = window.setTimeout(() => {
          console.log('Attempting to reconnect...');
          connect();
        }, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('Failed to connect:', e);
      setConnected(false);
    }
  }, [url]);

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

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }, []);

  return { connected, params, expression, sendMessage };
}
