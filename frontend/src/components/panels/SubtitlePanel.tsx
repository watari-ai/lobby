import React from 'react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { cn } from '../../lib/utils';

const FONTS = ['Noto Sans JP', 'M PLUS Rounded 1c', 'Kosugi Maru', 'Sawarabi Gothic'];

export function SubtitlePanel() {
  const { subtitle, setSubtitleEnabled, setSubtitleFont, setSubtitlePosition, setSubtitleBackground } = useLobbyStore();

  return (
    <div className="p-4 space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">Subtitle</h3>
        <button
          onClick={() => setSubtitleEnabled(!subtitle.enabled)}
          className={cn(
            "w-12 h-6 rounded-full transition-colors relative",
            subtitle.enabled ? "bg-green-500" : "bg-secondary"
          )}
        >
          <div
            className={cn(
              "w-5 h-5 rounded-full bg-white shadow absolute top-0.5 transition-transform",
              subtitle.enabled ? "translate-x-6" : "translate-x-0.5"
            )}
          />
        </button>
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-medium text-foreground">Font</h3>
        
        <div className="space-y-3">
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Family</label>
            <select
              value={subtitle.font.family}
              onChange={(e) => setSubtitleFont({ family: e.target.value })}
              className="w-full px-3 py-2 bg-secondary rounded-lg text-foreground border border-border focus:border-primary focus:outline-none"
            >
              {FONTS.map((font) => (
                <option key={font} value={font}>{font}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <label className="text-muted-foreground">Size</label>
              <span className="text-foreground">{subtitle.font.size}px</span>
            </div>
            <input
              type="range"
              min="16"
              max="64"
              value={subtitle.font.size}
              onChange={(e) => setSubtitleFont({ size: parseInt(e.target.value) })}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>

          <div className="flex gap-3">
            <div className="flex-1 space-y-2">
              <label className="text-xs text-muted-foreground">Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={subtitle.font.color}
                  onChange={(e) => setSubtitleFont({ color: e.target.value })}
                  className="w-8 h-8 rounded border border-border cursor-pointer"
                />
                <span className="text-sm text-foreground">{subtitle.font.color}</span>
              </div>
            </div>
            <div className="flex-1 space-y-2">
              <label className="text-xs text-muted-foreground">Weight</label>
              <select
                value={subtitle.font.weight}
                onChange={(e) => setSubtitleFont({ weight: parseInt(e.target.value) })}
                className="w-full px-3 py-2 bg-secondary rounded-lg text-foreground border border-border focus:border-primary focus:outline-none"
              >
                <option value={300}>Light</option>
                <option value={400}>Normal</option>
                <option value={500}>Medium</option>
                <option value={700}>Bold</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Position</h3>
        <div className="grid grid-cols-3 gap-1 p-2 bg-secondary rounded-lg">
          {(['top', 'middle', 'bottom'] as const).map((v) =>
            (['left', 'center', 'right'] as const).map((h) => (
              <button
                key={`${v}-${h}`}
                onClick={() => setSubtitlePosition({ vertical: v, horizontal: h })}
                className={cn(
                  "w-8 h-8 rounded flex items-center justify-center text-xs transition-colors",
                  subtitle.position.vertical === v && subtitle.position.horizontal === h
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-accent text-muted-foreground"
                )}
              >
                ●
              </button>
            ))
          )}
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-medium text-foreground">Background</h3>
        
        <div className="flex gap-3">
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Color</label>
            <input
              type="color"
              value={subtitle.background.color}
              onChange={(e) => setSubtitleBackground({ color: e.target.value })}
              className="w-8 h-8 rounded border border-border cursor-pointer"
            />
          </div>
          
          <div className="flex-1 space-y-2">
            <div className="flex justify-between text-xs">
              <label className="text-muted-foreground">Opacity</label>
              <span className="text-foreground">{Math.round(subtitle.background.opacity * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={subtitle.background.opacity}
              onChange={(e) => setSubtitleBackground({ opacity: parseFloat(e.target.value) })}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
