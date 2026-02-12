import React from 'react';
import { User, UserCircle, UserSquare2, Eye } from 'lucide-react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { cn } from '../../lib/utils';
import type { CameraPreset, CameraTransition } from '../../types';

const PRESETS: { id: CameraPreset; label: string; zoom: string; icon: React.ReactNode }[] = [
  { id: 'full', label: 'Full Body', zoom: '1.0x', icon: <User className="w-8 h-8" /> },
  { id: 'bust', label: 'Bust Up', zoom: '1.5x', icon: <UserCircle className="w-8 h-8" /> },
  { id: 'shoulder', label: 'Shoulder', zoom: '2.0x', icon: <UserSquare2 className="w-8 h-8" /> },
  { id: 'close', label: 'Close Up', zoom: '2.5x', icon: <Eye className="w-8 h-8" /> },
];

const TRANSITIONS: CameraTransition[] = ['cut', 'smooth', 'zoom'];

export function CameraPanel() {
  const { camera, setCameraPreset, setCameraZoom, setCameraOffset, setCameraTransition } = useLobbyStore();

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-sm font-medium text-foreground mb-3">Presets</h3>
        <div className="grid grid-cols-2 gap-3">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => setCameraPreset(preset.id)}
              className={cn(
                "flex flex-col items-center justify-center p-4 rounded-lg border transition-all",
                camera.preset === preset.id
                  ? "border-primary bg-accent text-accent-foreground"
                  : "border-border hover:border-primary/50 text-muted-foreground hover:text-foreground"
              )}
            >
              {preset.icon}
              <span className="text-sm mt-2">{preset.label}</span>
              <span className="text-xs text-muted-foreground">{preset.zoom}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-medium text-foreground">Manual Controls</h3>
        
        <div className="space-y-3">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <label className="text-muted-foreground">Zoom</label>
              <span className="text-foreground">{camera.zoom.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="3"
              step="0.1"
              value={camera.zoom}
              onChange={(e) => setCameraZoom(parseFloat(e.target.value))}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <label className="text-muted-foreground">Offset X</label>
              <span className="text-foreground">{camera.offsetX}</span>
            </div>
            <input
              type="range"
              min="-100"
              max="100"
              step="1"
              value={camera.offsetX}
              onChange={(e) => setCameraOffset(parseInt(e.target.value), camera.offsetY)}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <label className="text-muted-foreground">Offset Y</label>
              <span className="text-foreground">{camera.offsetY}</span>
            </div>
            <input
              type="range"
              min="-100"
              max="100"
              step="1"
              value={camera.offsetY}
              onChange={(e) => setCameraOffset(camera.offsetX, parseInt(e.target.value))}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Transition</h3>
        <div className="flex gap-2">
          {TRANSITIONS.map((t) => (
            <button
              key={t}
              onClick={() => setCameraTransition(t)}
              className={cn(
                "px-3 py-1.5 rounded text-sm capitalize transition-colors",
                camera.transition === t
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-accent"
              )}
            >
              {t}
            </button>
          ))}
        </div>
        
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <label className="text-muted-foreground">Duration</label>
            <span className="text-foreground">{camera.transitionDuration}ms</span>
          </div>
          <input
            type="range"
            min="100"
            max="2000"
            step="100"
            value={camera.transitionDuration}
            onChange={(e) => setCameraTransition(camera.transition, parseInt(e.target.value))}
            className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
          />
        </div>
      </div>
    </div>
  );
}
