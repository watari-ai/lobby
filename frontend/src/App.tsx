import React, { useState, useCallback } from 'react';
import Live2DViewer from './components/Live2DViewer';
import ControlPanel from './components/ControlPanel';
import { useLive2DWebSocket } from './hooks/useLive2DWebSocket';

const EXPRESSIONS = ['neutral', 'happy', 'sad', 'excited', 'surprised', 'angry'] as const;
type Expression = typeof EXPRESSIONS[number];

function App() {
  const [currentExpression, setCurrentExpression] = useState<Expression>('neutral');
  const { connected, params, sendMessage } = useLive2DWebSocket('ws://localhost:8000/ws/live2d');

  const handleExpressionChange = useCallback((expression: Expression) => {
    setCurrentExpression(expression);
    sendMessage({ action: 'set_expression', expression });
  }, [sendMessage]);

  const handleParamChange = useCallback((name: string, value: number) => {
    sendMessage({ action: 'set_param', name, value });
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
          <Live2DViewer params={params} />
        </div>
        
        <aside className="sidebar">
          <ControlPanel
            expressions={EXPRESSIONS}
            currentExpression={currentExpression}
            onExpressionChange={handleExpressionChange}
            onParamChange={handleParamChange}
            params={params}
          />
        </aside>
      </main>
    </div>
  );
}

export default App;
