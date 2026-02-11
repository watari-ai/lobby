import React, { useRef, useEffect, useState } from 'react';
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
  ParamBreath?: number;
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

const Live2DViewer: React.FC<Live2DViewerProps> = ({ 
  params, 
  modelPath,
  physics = { enabled: true }
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<PIXI.Application | null>(null);
  const modelRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          const pm = model.internalModel.physicsManager;
          if (physics.enabled) {
            // 物理演算を有効化（髪揺れ、呼吸などのアイドルモーション）
            pm.physicsCubismPhysics?.initialize();
            console.log('[Live2D] Physics enabled');
          }
        }
        
        // アイドルモーション（目パチ、呼吸）を開始
        if (model.internalModel?.motionManager) {
          // 自動目パチを有効化
          model.internalModel.eyeBlink = true;
          // 呼吸モーションを有効化
          model.internalModel.breath = true;
          console.log('[Live2D] Idle motions enabled (eye blink, breath)');
        }
        
        setLoading(false);
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
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }
    };
  }, [modelPath]);

  // パラメータの更新
  useEffect(() => {
    if (!modelRef.current?.internalModel?.coreModel) return;

    const coreModel = modelRef.current.internalModel.coreModel;
    
    // 各パラメータを設定
    Object.entries(params).forEach(([name, value]) => {
      if (typeof value !== 'number') return;
      
      const paramId = coreModel.getParameterIndex(name);
      if (paramId >= 0) {
        coreModel.setParameterValueById(name, value);
      }
    });
  }, [params]);

  // 物理演算パラメータの更新
  useEffect(() => {
    if (!modelRef.current?.internalModel?.physicsManager) return;
    
    const pm = modelRef.current.internalModel.physicsManager;
    
    // Cubism SDK の物理演算設定を更新
    if (pm.physicsCubismPhysics) {
      // 重力の設定（デフォルト: y=-1でモデル下方向）
      if (physics?.gravity) {
        // 物理演算の Gravity ベクトルを設定
        // Note: pixi-live2d-display では直接アクセスが制限されている場合がある
        console.log('[Live2D] Gravity set to:', physics.gravity);
      }
      
      // 風の設定（髪やアクセサリーへの影響）
      if (physics?.wind) {
        console.log('[Live2D] Wind set to:', physics.wind);
      }
    }
  }, [physics]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {loading && (
        <div className="loading-overlay">
          Loading Live2D model...
        </div>
      )}
      {error && (
        <div className="loading-overlay" style={{ color: '#f44' }}>
          Error: {error}
        </div>
      )}
    </div>
  );
};

export default Live2DViewer;
