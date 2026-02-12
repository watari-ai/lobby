import React, { useState, useEffect } from 'react';
import { Circle } from 'lucide-react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { useBackend } from '../../contexts/BackendContext';
import { cn } from '../../lib/utils';

export function StatusBar() {
  const { camera, audio, subtitle, expression } = useLobbyStore();
  const { connected, reconnectAttempts } = useBackend();
  const [fps, setFps] = useState(60);

  // Simple FPS counter simulation
  useEffect(() => {
    let frameCount = 0;
    let lastTime = performance.now();
    
    const countFrame = () => {
      frameCount++;
      const currentTime = performance.now();
      if (currentTime - lastTime >= 1000) {
        setFps(frameCount);
        frameCount = 0;
        lastTime = currentTime;
      }
      requestAnimationFrame(countFrame);
    };
    
    const animId = requestAnimationFrame(countFrame);
    return () => cancelAnimationFrame(animId);
  }, []);

  const connectionStatus = connected 
    ? 'Connected' 
    : reconnectAttempts > 0 
      ? `Reconnecting (${reconnectAttempts}/10)` 
      : 'Disconnected';

  return (
    <footer className="h-8 border-t border-border bg-background/95 flex items-center justify-between px-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Circle
            className={cn(
              "w-2 h-2 fill-current",
              connected ? "text-green-500" : reconnectAttempts > 0 ? "text-yellow-500" : "text-red-500"
            )}
          />
          <span>Backend: {connectionStatus}</span>
        </div>
        <span className="text-primary/70">Expression: {expression}</span>
      </div>
      
      <div className="flex items-center gap-4">
        <span>Camera: {camera.preset}</span>
        <span>BGM: {audio.bgm.playing ? 'Playing' : 'Stopped'}</span>
        <span>Subtitle: {subtitle.enabled ? 'ON' : 'OFF'}</span>
        <span>FPS: {fps}</span>
      </div>
    </footer>
  );
}
