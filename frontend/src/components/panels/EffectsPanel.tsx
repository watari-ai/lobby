import React from 'react';
import { X } from 'lucide-react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { cn } from '../../lib/utils';
import type { EffectType, FilterType } from '../../types';

const EFFECTS: { id: EffectType; icon: string; label: string }[] = [
  { id: 'confetti', icon: '🎊', label: 'Confetti' },
  { id: 'fireworks', icon: '🎆', label: 'Firework' },
  { id: 'hearts', icon: '💕', label: 'Hearts' },
  { id: 'stars', icon: '⭐', label: 'Stars' },
  { id: 'snow', icon: '❄️', label: 'Snow' },
  { id: 'rain', icon: '🌧️', label: 'Rain' },
  { id: 'flash', icon: '⚡', label: 'Flash' },
  { id: 'shake', icon: '📸', label: 'Shake' },
];

const FILTERS: { id: FilterType; label: string }[] = [
  { id: 'none', label: 'None' },
  { id: 'blur', label: 'Blur' },
  { id: 'vignette', label: 'Vignette' },
];

export function EffectsPanel() {
  const { effects, triggerEffect, stopEffect, setFilter } = useLobbyStore();

  return (
    <div className="p-4 space-y-6">
      <div>
        <h3 className="text-sm font-medium text-foreground mb-3">Screen Effects</h3>
        <div className="grid grid-cols-4 gap-2">
          {EFFECTS.map((effect) => (
            <button
              key={effect.id}
              onClick={() => triggerEffect(effect.id)}
              className="flex flex-col items-center justify-center p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-accent transition-colors"
            >
              <span className="text-2xl">{effect.icon}</span>
              <span className="text-xs mt-1 text-muted-foreground">{effect.label}</span>
            </button>
          ))}
        </div>
      </div>

      {effects.activeEffects.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-foreground">Active Effects</h3>
            <button
              onClick={() => stopEffect()}
              className="text-xs text-red-400 hover:text-red-300 transition-colors"
            >
              Clear All
            </button>
          </div>
          <div className="space-y-2">
            {effects.activeEffects.map((effect) => {
              const effectInfo = EFFECTS.find((e) => e.id === effect.type);
              return (
                <div
                  key={effect.id}
                  className="flex items-center justify-between px-3 py-2 bg-secondary rounded-lg"
                >
                  <div className="flex items-center gap-2">
                    <span>{effectInfo?.icon}</span>
                    <span className="text-sm text-foreground capitalize">{effect.type}</span>
                  </div>
                  <button
                    onClick={() => stopEffect(effect.id)}
                    className="p-1 rounded hover:bg-accent transition-colors"
                  >
                    <X className="w-4 h-4 text-muted-foreground" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">Filters</h3>
        <div className="flex gap-2">
          {FILTERS.map((filter) => (
            <button
              key={filter.id}
              onClick={() => setFilter(filter.id)}
              className={cn(
                "flex-1 px-3 py-2 rounded-lg text-sm transition-colors",
                effects.filter === filter.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-accent"
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
