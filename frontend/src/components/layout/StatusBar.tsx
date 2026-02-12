import React, { useState, useEffect } from 'react';
import { Circle } from 'lucide-react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { cn } from '../../lib/utils';

export function StatusBar() {
  const { connected, camera, audio, subtitle } = useLobbyStore();
  const [fps, setFps] = useState(60);
  const [cpu, setCpu] = useState(0);

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

  return (
    <footer className="h-8 border-t border-border bg-background/95 flex items-center justify-between px-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Circle
            className={cn(
              "w-2 h-2 fill-current",
              connected ? "text-green-500" : "text-red-500"
            )}
          />
          <span>Backend: localhost:8000</span>
        </div>
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
