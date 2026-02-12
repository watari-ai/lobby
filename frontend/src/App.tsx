import React, { useState } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar, type PanelType } from './components/layout/Sidebar';
import { StatusBar } from './components/layout/StatusBar';
import { CameraPanel } from './components/panels/CameraPanel';
import { BackgroundPanel } from './components/panels/BackgroundPanel';
import { SubtitlePanel } from './components/panels/SubtitlePanel';
import { AudioPanel } from './components/panels/AudioPanel';
import { EffectsPanel } from './components/panels/EffectsPanel';
import { SettingsPanel } from './components/panels/SettingsPanel';
import Live2DViewer from './components/Live2DViewer';
import SubtitleDisplay from './components/SubtitleDisplay';
import StreamingIndicator from './components/StreamingIndicator';
import { UpdateNotification } from './components/UpdateNotification';
import { useLobbyStore } from './stores/lobbyStore';
import { useBackend } from './contexts/BackendContext';

// Panel title mapping
const PANEL_TITLES: Record<PanelType, string> = {
  camera: '📷 Camera',
  background: '🖼️ Background',
  subtitle: '💬 Subtitle',
  audio: '🎵 Audio',
  effects: '✨ Effects',
  settings: '⚙️ Settings',
};

function App() {
  const [activePanel, setActivePanel] = useState<PanelType>('camera');
  const { physics, subtitle, camera, live2dParams } = useLobbyStore();
  
  // Backend WebSocket sync (auto-reconnect, bidirectional)
  const { connected, reconnect, reconnectAttempts } = useBackend();

  const renderPanel = () => {
    switch (activePanel) {
      case 'camera':
        return <CameraPanel />;
      case 'background':
        return <BackgroundPanel />;
      case 'subtitle':
        return <SubtitlePanel />;
      case 'audio':
        return <AudioPanel />;
      case 'effects':
        return <EffectsPanel />;
      case 'settings':
        return <SettingsPanel />;
      default:
        return null;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />
      
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activePanel={activePanel} onPanelChange={setActivePanel} />
        
        {/* Control Panel */}
        <div className="w-80 border-r border-border bg-background overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-sm font-medium text-foreground">
              {PANEL_TITLES[activePanel]}
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            {renderPanel()}
          </div>
        </div>
        
        {/* Preview Area */}
        <main className="flex-1 flex flex-col p-4 overflow-hidden">
          {/* Connection Status Banner */}
          {!connected && (
            <div className="mb-2 px-3 py-2 bg-yellow-500/20 border border-yellow-500/50 rounded-lg flex items-center justify-between">
              <span className="text-yellow-200 text-sm">
                ⚠️ Backend disconnected {reconnectAttempts > 0 && `(retry ${reconnectAttempts}/10)`}
              </span>
              <button
                onClick={reconnect}
                className="px-2 py-1 text-xs bg-yellow-600 hover:bg-yellow-500 rounded transition-colors"
              >
                Reconnect
              </button>
            </div>
          )}
          
          <div 
            className="flex-1 relative rounded-lg overflow-hidden"
            style={{ 
              backgroundColor: useLobbyStore.getState().background.source,
              transform: `scale(${camera.zoom}) translate(${camera.offsetX}px, ${camera.offsetY}px)`,
              transformOrigin: 'center center',
              transition: camera.transition === 'smooth' 
                ? `transform ${camera.transitionDuration}ms ease-out` 
                : 'none',
            }}
          >
            {/* Live2D Realtime Preview */}
            <Live2DViewer 
              params={live2dParams} 
              physics={physics}
              smoothing={0.25}
            />
            
            {/* Streaming Status Indicator */}
            <StreamingIndicator position="top-right" detailed={false} />
            
            {subtitle.enabled && (
              <SubtitleDisplay 
                position={subtitle.position.vertical === 'middle' ? 'center' : subtitle.position.vertical} 
                backgroundOpacity={subtitle.background.opacity}
              />
            )}
          </div>
          
          {/* Quick Actions */}
          <div className="mt-4 flex items-center justify-between">
            <div className="flex gap-2">
              {['full', 'bust', 'shoulder'].map((preset) => (
                <button
                  key={preset}
                  onClick={() => useLobbyStore.getState().setCameraPreset(preset as any)}
                  className={`px-3 py-1.5 rounded text-sm capitalize transition-colors ${
                    camera.preset === preset
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-secondary-foreground hover:bg-accent'
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => useLobbyStore.getState().triggerEffect('confetti')}
                className="px-3 py-1.5 rounded text-sm bg-secondary hover:bg-accent transition-colors"
              >
                🎊 Confetti
              </button>
              <button
                onClick={() => useLobbyStore.getState().setBgmPlaying(!useLobbyStore.getState().audio.bgm.playing)}
                className="px-3 py-1.5 rounded text-sm bg-secondary hover:bg-accent transition-colors"
              >
                {useLobbyStore.getState().audio.bgm.playing ? '⏸ Pause' : '▶ Play'} BGM
              </button>
            </div>
          </div>
        </main>
      </div>
      
      <StatusBar />
      
      {/* Auto-update notification (Electron only) */}
      <UpdateNotification />
    </div>
  );
}

export default App;
