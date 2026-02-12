/**
 * StreamingIndicator - リアルタイムストリーミング状態表示
 * 
 * バックエンドからのLive2Dパラメータストリーム状態を可視化
 */

import React, { useState, useEffect, useRef } from 'react';
import { useLobbyStore } from '../stores/lobbyStore';

interface StreamingIndicatorProps {
  /** 表示位置 */
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  /** 詳細表示モード */
  detailed?: boolean;
}

const StreamingIndicator: React.FC<StreamingIndicatorProps> = ({
  position = 'top-right',
  detailed = false,
}) => {
  const connected = useLobbyStore((state) => state.connected);
  const live2dParams = useLobbyStore((state) => state.live2dParams);
  
  // パラメータ更新頻度を計測
  const [updateRate, setUpdateRate] = useState(0);
  const updateCountRef = useRef(0);
  const lastParamsRef = useRef<string>('');
  
  useEffect(() => {
    // パラメータが変更されたらカウント
    const paramsJson = JSON.stringify(live2dParams);
    if (paramsJson !== lastParamsRef.current) {
      lastParamsRef.current = paramsJson;
      updateCountRef.current++;
    }
  }, [live2dParams]);
  
  // 1秒ごとに更新レートを計算
  useEffect(() => {
    const interval = setInterval(() => {
      setUpdateRate(updateCountRef.current);
      updateCountRef.current = 0;
    }, 1000);
    
    return () => clearInterval(interval);
  }, []);
  
  // 位置クラス
  const positionClasses: Record<string, string> = {
    'top-left': 'top-2 left-2',
    'top-right': 'top-2 right-2',
    'bottom-left': 'bottom-2 left-2',
    'bottom-right': 'bottom-2 right-2',
  };
  
  // 状態に応じたスタイル
  const getStatusStyle = () => {
    if (!connected) {
      return 'bg-red-500/20 border-red-500/50 text-red-200';
    }
    if (updateRate > 30) {
      return 'bg-green-500/20 border-green-500/50 text-green-200';
    }
    if (updateRate > 0) {
      return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-200';
    }
    return 'bg-gray-500/20 border-gray-500/50 text-gray-300';
  };
  
  // 状態アイコン
  const getStatusIcon = () => {
    if (!connected) return '🔴';
    if (updateRate > 30) return '🟢';
    if (updateRate > 0) return '🟡';
    return '⚪';
  };
  
  // 状態テキスト
  const getStatusText = () => {
    if (!connected) return 'Disconnected';
    if (updateRate > 30) return 'Streaming';
    if (updateRate > 0) return 'Active';
    return 'Idle';
  };
  
  return (
    <div
      className={`absolute ${positionClasses[position]} z-10`}
    >
      <div
        className={`px-3 py-2 rounded-lg border backdrop-blur-sm ${getStatusStyle()}`}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm">{getStatusIcon()}</span>
          <span className="text-sm font-medium">{getStatusText()}</span>
          {connected && (
            <span className="text-xs opacity-70">{updateRate} fps</span>
          )}
        </div>
        
        {detailed && connected && (
          <div className="mt-2 text-xs font-mono opacity-80">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <span>Mouth:</span>
              <span>{(live2dParams.ParamMouthOpenY ?? 0).toFixed(2)}</span>
              <span>EyeL:</span>
              <span>{(live2dParams.ParamEyeLOpen ?? 1).toFixed(2)}</span>
              <span>EyeR:</span>
              <span>{(live2dParams.ParamEyeROpen ?? 1).toFixed(2)}</span>
              <span>AngleX:</span>
              <span>{(live2dParams.ParamAngleX ?? 0).toFixed(2)}</span>
              <span>AngleY:</span>
              <span>{(live2dParams.ParamAngleY ?? 0).toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default StreamingIndicator;
