import React, { useState, useCallback } from 'react';
import Live2DViewer from './components/Live2DViewer';
import ControlPanel from './components/ControlPanel';
import { useLive2DWebSocket } from './hooks/useLive2DWebSocket';

const EXPRESSIONS = ['neutral', 'happy', 'sad', 'excited', 'surprised', 'angry'] as const;
type Expression = typeof EXPRESSIONS[number];

interface PhysicsConfig {
  enabled: boolean;
  gravity?: { x: number; y: number };
  wind?: { x: number; y: number };
}

function App() {
  const [currentExpression, setCurrentExpression] = useState<Expression>('neutral');
  const [physics, setPhysics] = useState<PhysicsConfig>({
    enabled: true,
    gravity: { x: 0, y: -1 },
    wind: { x: 0, y: 0 },
  });
  const { connected, params, sendMessage } = useLive2DWebSocket('ws://localhost:8000/ws/live2d');

  const handleExpressionChange = useCallback((expression: Expression) => {
    setCurrentExpression(expression);
    sendMessage({ action: 'set_expression', expression });
  }, [sendMessage]);

  const handleParamChange = useCallback((name: string, value: number) => {
    sendMessage({ action: 'set_param', name, value });
  }, [sendMessage]);

  const handlePhysicsChange = useCallback((newPhysics: PhysicsConfig) => {
    setPhysics(newPhysics);
    sendMessage({ action: 'set_physics', physics: newPhysics });
  }, [sendMessage]);

  return (
    <div className="app">
      <header className="header">
        <h1>🦞 Lobby</h1>
        <div className={`connection-status ${connected ? 'connected' : ''}`}>
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>
      
      <main className="main">
        <div className="canvas-container">
          <Live2DViewer params={params} physics={physics} />
        </div>
        
        <aside className="sidebar">
          <ControlPanel
            expressions={EXPRESSIONS}
            currentExpression={currentExpression}
            onExpressionChange={handleExpressionChange}
            onParamChange={handleParamChange}
            params={params}
            physics={physics}
            onPhysicsChange={handlePhysicsChange}
          />
        </aside>
      </main>
    </div>
  );
}

export default App;
