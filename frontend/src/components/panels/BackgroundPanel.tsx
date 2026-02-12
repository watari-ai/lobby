import React from 'react';
import { Image, Video, Palette, Upload } from 'lucide-react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { cn } from '../../lib/utils';
import type { BackgroundType } from '../../types';

const BG_TYPES: { id: BackgroundType; icon: React.ReactNode; label: string }[] = [
  { id: 'image', icon: <Image className="w-4 h-4" />, label: 'Image' },
  { id: 'video', icon: <Video className="w-4 h-4" />, label: 'Video' },
  { id: 'color', icon: <Palette className="w-4 h-4" />, label: 'Color' },
];

const PRESET_ICONS: Record<string, string> = {
  room: '🏠',
  city: '🌃',
  park: '🌸',
  game: '🎮',
};

export function BackgroundPanel() {
  const { background, setBackgroundType, setBackgroundSource } = useLobbyStore();

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-sm font-medium text-foreground mb-3">Type</h3>
        <div className="flex gap-2">
          {BG_TYPES.map((type) => (
            <button
              key={type.id}
              onClick={() => setBackgroundType(type.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg transition-colors",
                background.type === type.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-accent"
              )}
            >
              {type.icon}
              <span className="text-sm">{type.label}</span>
            </button>
          ))}
        </div>
      </div>

      {background.type === 'color' && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-foreground">Color</h3>
          <div className="flex items-center gap-3">
            <input
              type="color"
              value={background.source}
              onChange={(e) => setBackgroundSource(e.target.value)}
              className="w-12 h-12 rounded-lg border border-border cursor-pointer"
            />
            <input
              type="text"
              value={background.source}
              onChange={(e) => setBackgroundSource(e.target.value)}
              className="flex-1 px-3 py-2 bg-secondary rounded-lg text-foreground border border-border focus:border-primary focus:outline-none"
              placeholder="#000000"
            />
          </div>
        </div>
      )}

      {(background.type === 'image' || background.type === 'video') && (
        <>
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3">Presets</h3>
            <div className="grid grid-cols-4 gap-2">
              {background.presets
                .filter((p) => p.type === background.type)
                .map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => setBackgroundSource(preset.source)}
                    className={cn(
                      "flex flex-col items-center justify-center p-3 rounded-lg border transition-all",
                      background.source === preset.source
                        ? "border-primary bg-accent"
                        : "border-border hover:border-primary/50"
                    )}
                  >
                    <span className="text-2xl">{PRESET_ICONS[preset.id] || '🖼️'}</span>
                    <span className="text-xs mt-1 text-muted-foreground">{preset.name}</span>
                  </button>
                ))}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-foreground mb-3">Custom</h3>
            <button className="w-full flex items-center justify-center gap-2 p-4 border-2 border-dashed border-border rounded-lg text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors">
              <Upload className="w-5 h-5" />
              <span>Upload Custom</span>
            </button>
          </div>
        </>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Transition</h3>
        <div className="flex gap-2">
          {['Fade', 'Slide', 'None'].map((t) => (
            <button
              key={t}
              className="px-3 py-1.5 rounded text-sm bg-secondary text-secondary-foreground hover:bg-accent transition-colors"
            >
              {t}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
