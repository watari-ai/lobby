import React from 'react';

interface PhysicsConfig {
  enabled: boolean;
  gravity?: { x: number; y: number };
  wind?: { x: number; y: number };
}

interface ControlPanelProps {
  expressions: readonly string[];
  currentExpression: string;
  onExpressionChange: (expression: string) => void;
  onParamChange: (name: string, value: number) => void;
  params: Record<string, number>;
  physics?: PhysicsConfig;
  onPhysicsChange?: (physics: PhysicsConfig) => void;
}

const PARAM_SLIDERS = [
  { name: 'ParamMouthOpenY', label: '口の開き', min: 0, max: 1, step: 0.01 },
  { name: 'ParamMouthForm', label: '口の形', min: -1, max: 1, step: 0.01 },
  { name: 'ParamEyeLOpen', label: '左目', min: 0, max: 1, step: 0.01 },
  { name: 'ParamEyeROpen', label: '右目', min: 0, max: 1, step: 0.01 },
  { name: 'ParamAngleX', label: '顔の向き(横)', min: -30, max: 30, step: 1 },
  { name: 'ParamAngleY', label: '顔の向き(縦)', min: -30, max: 30, step: 1 },
  { name: 'ParamBrowLY', label: '左眉', min: -1, max: 1, step: 0.01 },
  { name: 'ParamBrowRY', label: '右眉', min: -1, max: 1, step: 0.01 },
];

const EXPRESSION_LABELS: Record<string, string> = {
  neutral: '😐 普通',
  happy: '😊 嬉しい',
  sad: '😢 悲しい',
  excited: '🤩 興奮',
  surprised: '😲 驚き',
  angry: '😠 怒り',
};

const ControlPanel: React.FC<ControlPanelProps> = ({
  expressions,
  currentExpression,
  onExpressionChange,
  onParamChange,
  params,
  physics = { enabled: true, gravity: { x: 0, y: -1 }, wind: { x: 0, y: 0 } },
  onPhysicsChange,
}) => {
  const handlePhysicsToggle = () => {
    onPhysicsChange?.({ ...physics, enabled: !physics.enabled });
  };

  const handleGravityChange = (axis: 'x' | 'y', value: number) => {
    onPhysicsChange?.({
      ...physics,
      gravity: { ...physics.gravity!, [axis]: value },
    });
  };

  const handleWindChange = (axis: 'x' | 'y', value: number) => {
    onPhysicsChange?.({
      ...physics,
      wind: { ...physics.wind!, [axis]: value },
    });
  };

  return (
    <>
      <div className="panel">
        <h3>表情</h3>
        <div className="expression-grid">
          {expressions.map((expr) => (
            <button
              key={expr}
              className={`expression-btn ${currentExpression === expr ? 'active' : ''}`}
              onClick={() => onExpressionChange(expr)}
            >
              {EXPRESSION_LABELS[expr] || expr}
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <h3>パラメータ</h3>
        {PARAM_SLIDERS.map(({ name, label, min, max, step }) => (
          <div key={name} className="param-slider">
            <label>
              <span>{label}</span>
              <span>{(params[name] ?? 0).toFixed(2)}</span>
            </label>
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={params[name] ?? 0}
              onChange={(e) => onParamChange(name, parseFloat(e.target.value))}
            />
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>🌊 物理演算</h3>
        <div className="physics-toggle">
          <label>
            <input
              type="checkbox"
              checked={physics.enabled}
              onChange={handlePhysicsToggle}
            />
            <span>物理演算を有効化（髪揺れ、呼吸等）</span>
          </label>
        </div>
        
        {physics.enabled && (
          <>
            <div className="param-slider">
              <label>
                <span>重力 X</span>
                <span>{physics.gravity?.x?.toFixed(2) ?? 0}</span>
              </label>
              <input
                type="range"
                min={-2}
                max={2}
                step={0.1}
                value={physics.gravity?.x ?? 0}
                onChange={(e) => handleGravityChange('x', parseFloat(e.target.value))}
              />
            </div>
            <div className="param-slider">
              <label>
                <span>重力 Y</span>
                <span>{physics.gravity?.y?.toFixed(2) ?? -1}</span>
              </label>
              <input
                type="range"
                min={-2}
                max={2}
                step={0.1}
                value={physics.gravity?.y ?? -1}
                onChange={(e) => handleGravityChange('y', parseFloat(e.target.value))}
              />
            </div>
            <div className="param-slider">
              <label>
                <span>風 X（左右）</span>
                <span>{physics.wind?.x?.toFixed(2) ?? 0}</span>
              </label>
              <input
                type="range"
                min={-2}
                max={2}
                step={0.1}
                value={physics.wind?.x ?? 0}
                onChange={(e) => handleWindChange('x', parseFloat(e.target.value))}
              />
            </div>
            <div className="param-slider">
              <label>
                <span>風 Y（上下）</span>
                <span>{physics.wind?.y?.toFixed(2) ?? 0}</span>
              </label>
              <input
                type="range"
                min={-2}
                max={2}
                step={0.1}
                value={physics.wind?.y ?? 0}
                onChange={(e) => handleWindChange('y', parseFloat(e.target.value))}
              />
            </div>
          </>
        )}
      </div>
    </>
  );
};

export default ControlPanel;
