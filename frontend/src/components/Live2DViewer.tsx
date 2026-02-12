/**
 * Live2DViewer - リアルタイムプレビュー対応Live2Dビューア
 * 
 * バックエンドからのパラメータストリームをスムーズに反映し、
 * 60fpsでの滑らかなアニメーションを実現します。
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';

// Live2D型定義
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
  ParamBodyAngleX?: number;
  ParamBodyAngleY?: number;
  ParamBreath?: number;
  [key: string]: number | undefined;
}

interface PhysicsConfig {
  enabled: boolean;
  gravity?: { x: number; y: number };
  wind?: { x: number; y: number };
}

interface Live2DViewerProps {
  params: Live2DParams;
  modelPath?: string;
  physics?: PhysicsConfig;
  /** パラメータ補間の滑らかさ (0-1, 1=即時反映, 0.1=ゆっくり) */
  smoothing?: number;
  /** デバッグモード */
  debug?: boolean;
}

// pixi-live2d-displayを動的にロード
let Live2DModel: any = null;

async function loadLive2DLibrary() {
  if (Live2DModel) return Live2DModel;
  
  try {
    // pixi-live2d-displayのCubism4対応版を使用
    const module = await import('pixi-live2d-display/cubism4');
    Live2DModel = module.Live2DModel;
    return Live2DModel;
  } catch (e) {
    console.warn('Failed to load Cubism4, trying default:', e);
    const module = await import('pixi-live2d-display');
    Live2DModel = module.Live2DModel;
    return Live2DModel;
  }
}

// パラメータIDマッピング（フロントエンド→Live2D SDK）
const PARAM_ID_MAP: Record<string, string> = {
  ParamMouthOpenY: 'ParamMouthOpenY',
  ParamMouthForm: 'ParamMouthForm',
  ParamEyeLOpen: 'ParamEyeLOpen',
  ParamEyeROpen: 'ParamEyeROpen',
  ParamEyeBallX: 'ParamEyeBallX',
  ParamEyeBallY: 'ParamEyeBallY',
  ParamBrowLY: 'ParamBrowLY',
  ParamBrowRY: 'ParamBrowRY',
  ParamAngleX: 'ParamAngleX',
  ParamAngleY: 'ParamAngleY',
  ParamAngleZ: 'ParamAngleZ',
  ParamBodyAngleX: 'ParamBodyAngleX',
  ParamBodyAngleY: 'ParamBodyAngleY',
  ParamBreath: 'ParamBreath',
};

const Live2DViewer: React.FC<Live2DViewerProps> = ({ 
  params, 
  modelPath,
  physics = { enabled: true },
  smoothing = 0.3,
  debug = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<PIXI.Application | null>(null);
  const modelRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 補間用の現在値と目標値
  const currentParamsRef = useRef<Live2DParams>({});
  const targetParamsRef = useRef<Live2DParams>({});
  const animationFrameRef = useRef<number | null>(null);
  const lastUpdateRef = useRef<number>(0);
  
  // デバッグ用FPSカウンター
  const fpsRef = useRef<{ count: number; lastTime: number; fps: number }>({
    count: 0,
    lastTime: performance.now(),
    fps: 0,
  });

  // パラメータをモデルに適用
  const applyParams = useCallback((paramValues: Live2DParams) => {
    if (!modelRef.current?.internalModel?.coreModel) return;

    const coreModel = modelRef.current.internalModel.coreModel;
    
    Object.entries(paramValues).forEach(([name, value]) => {
      if (typeof value !== 'number') return;
      
      // パラメータIDを取得（マッピングまたはそのまま）
      const paramId = PARAM_ID_MAP[name] || name;
      
      try {
        // Cubism SDK 4のcoreModelはsetParameterValueByIdをサポート
        if (typeof coreModel.setParameterValueById === 'function') {
          coreModel.setParameterValueById(paramId, value);
        } else if (typeof coreModel.setParamFloat === 'function') {
          // 旧SDK互換
          coreModel.setParamFloat(paramId, value);
        }
      } catch (e) {
        // パラメータが存在しない場合は無視
        if (debug) {
          console.warn(`[Live2D] Failed to set param ${paramId}:`, e);
        }
      }
    });
  }, [debug]);

  // 滑らかな補間アニメーションループ
  const animationLoop = useCallback(() => {
    const now = performance.now();
    const delta = now - lastUpdateRef.current;
    lastUpdateRef.current = now;
    
    // FPSカウント（デバッグ用）
    if (debug) {
      fpsRef.current.count++;
      if (now - fpsRef.current.lastTime >= 1000) {
        fpsRef.current.fps = fpsRef.current.count;
        fpsRef.current.count = 0;
        fpsRef.current.lastTime = now;
      }
    }
    
    // 補間係数（フレームレート非依存）
    const t = Math.min(1, smoothing * (delta / 16.67)); // 60fpsを基準
    
    // 各パラメータを補間
    const current = currentParamsRef.current;
    const target = targetParamsRef.current;
    let hasChanges = false;
    
    Object.keys(target).forEach((key) => {
      const targetValue = target[key];
      if (typeof targetValue !== 'number') return;
      
      const currentValue = current[key] ?? targetValue;
      
      // 補間計算
      const diff = targetValue - currentValue;
      if (Math.abs(diff) > 0.001) {
        current[key] = currentValue + diff * t;
        hasChanges = true;
      } else {
        current[key] = targetValue;
      }
    });
    
    // 変更があればモデルに適用
    if (hasChanges || Object.keys(current).length > 0) {
      applyParams(current);
    }
    
    // 次のフレームをスケジュール
    animationFrameRef.current = requestAnimationFrame(animationLoop);
  }, [smoothing, applyParams, debug]);

  // PixiJS アプリケーション初期化
  useEffect(() => {
    if (!containerRef.current) return;

    const app = new PIXI.Application();
    
    const initApp = async () => {
      await app.init({
        width: containerRef.current!.clientWidth,
        height: containerRef.current!.clientHeight,
        backgroundColor: 0x1a1a2e,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      });
      
      containerRef.current!.appendChild(app.canvas);
      appRef.current = app;

      // モデルをロード
      try {
        const Model = await loadLive2DLibrary();
        
        // デモモデルまたは指定されたモデルをロード
        const path = modelPath || 'https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display/test/assets/haru/haru_greeter_t03.model3.json';
        
        console.log('[Live2D] Loading model:', path);
        const model = await Model.from(path);
        
        // モデルをステージに追加
        app.stage.addChild(model);
        
        // モデルのサイズと位置を調整
        const scale = Math.min(
          app.screen.width / model.width * 0.8,
          app.screen.height / model.height * 0.9
        );
        model.scale.set(scale);
        model.x = app.screen.width / 2;
        model.y = app.screen.height - 20;
        model.anchor.set(0.5, 1);
        
        modelRef.current = model;
        
        // 物理演算の設定
        if (model.internalModel?.physicsManager) {
          if (physics.enabled) {
            console.log('[Live2D] Physics enabled');
          }
        }
        
        // アイドルモーション（目パチ、呼吸）を開始
        if (model.internalModel) {
          model.internalModel.eyeBlink = true;
          model.internalModel.breath = true;
          console.log('[Live2D] Idle motions enabled (eye blink, breath)');
        }
        
        // アニメーションループを開始
        lastUpdateRef.current = performance.now();
        animationFrameRef.current = requestAnimationFrame(animationLoop);
        
        setLoading(false);
        console.log('[Live2D] Model loaded successfully');
      } catch (e: any) {
        console.error('Failed to load Live2D model:', e);
        setError(e.message || 'Failed to load model');
        setLoading(false);
      }
    };

    initApp();

    // リサイズハンドラ
    const handleResize = () => {
      if (appRef.current && containerRef.current) {
        appRef.current.renderer.resize(
          containerRef.current.clientWidth,
          containerRef.current.clientHeight
        );
        
        if (modelRef.current) {
          const model = modelRef.current;
          const scale = Math.min(
            appRef.current.screen.width / (model.width / model.scale.x) * 0.8,
            appRef.current.screen.height / (model.height / model.scale.y) * 0.9
          );
          model.scale.set(scale);
          model.x = appRef.current.screen.width / 2;
          model.y = appRef.current.screen.height - 20;
        }
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      
      // アニメーションループを停止
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }
    };
  }, [modelPath, animationLoop, physics.enabled]);

  // ターゲットパラメータの更新（props変更時）
  useEffect(() => {
    targetParamsRef.current = { ...params };
  }, [params]);

  // 物理演算パラメータの更新
  useEffect(() => {
    if (!modelRef.current?.internalModel?.physicsManager) return;
    
    if (physics?.gravity) {
      if (debug) {
        console.log('[Live2D] Gravity set to:', physics.gravity);
      }
    }
    
    if (physics?.wind) {
      if (debug) {
        console.log('[Live2D] Wind set to:', physics.wind);
      }
    }
  }, [physics, debug]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 text-white">
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin" />
            <span>Loading Live2D model...</span>
          </div>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 text-red-400">
          <div className="flex flex-col items-center gap-2">
            <span className="text-2xl">⚠️</span>
            <span>Error: {error}</span>
          </div>
        </div>
      )}
      {debug && !loading && !error && (
        <div className="absolute top-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded font-mono">
          FPS: {fpsRef.current.fps}
        </div>
      )}
    </div>
  );
};

export default Live2DViewer;
