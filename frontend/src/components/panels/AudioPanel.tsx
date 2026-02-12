import React from 'react';
import { Play, Pause, SkipBack, SkipForward, Volume2, Plus } from 'lucide-react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { cn } from '../../lib/utils';

export function AudioPanel() {
  const { audio, setBgmPlaying, setBgmVolume, setSeVolume } = useLobbyStore();

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="p-4 space-y-6">
      <div className="space-y-4">
        <h3 className="text-sm font-medium text-foreground">BGM</h3>
        
        <div className="p-4 bg-secondary rounded-lg space-y-4">
          <div className="text-center">
            <p className="text-sm text-foreground">
              {audio.bgm.currentTrack?.name || 'No track selected'}
            </p>
          </div>

          <div className="flex items-center justify-center gap-4">
            <button className="p-2 rounded-full hover:bg-accent transition-colors">
              <SkipBack className="w-5 h-5 text-muted-foreground" />
            </button>
            <button
              onClick={() => setBgmPlaying(!audio.bgm.playing)}
              className="p-3 rounded-full bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
            >
              {audio.bgm.playing ? (
                <Pause className="w-5 h-5" />
              ) : (
                <Play className="w-5 h-5 ml-0.5" />
              )}
            </button>
            <button className="p-2 rounded-full hover:bg-accent transition-colors">
              <SkipForward className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>

          <div className="space-y-2">
            <div className="h-1 bg-accent rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${audio.bgm.progress * 100}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{formatTime(audio.bgm.progress * (audio.bgm.currentTrack?.duration || 0))}</span>
              <span>{formatTime(audio.bgm.currentTrack?.duration || 0)}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-muted-foreground" />
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={audio.bgm.volume}
              onChange={(e) => setBgmVolume(parseFloat(e.target.value))}
              className="flex-1 h-2 bg-accent rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Playlist</span>
            <button className="text-xs text-primary hover:underline flex items-center gap-1">
              <Plus className="w-3 h-3" />
              Add Track
            </button>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {audio.bgm.playlist.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">
                No tracks in playlist
              </p>
            ) : (
              audio.bgm.playlist.map((track) => (
                <div
                  key={track.id}
                  className={cn(
                    "flex items-center justify-between px-3 py-2 rounded transition-colors cursor-pointer",
                    audio.bgm.currentTrack?.id === track.id
                      ? "bg-accent"
                      : "hover:bg-accent/50"
                  )}
                >
                  <span className="text-sm text-foreground">{track.name}</span>
                  <span className="text-xs text-muted-foreground">{formatTime(track.duration)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-foreground">Sound Effects</h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Volume2 className="w-3 h-3" />
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={audio.se.volume}
              onChange={(e) => setSeVolume(parseFloat(e.target.value))}
              className="w-20 h-1.5 bg-accent rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>
        </div>
        
        <div className="grid grid-cols-4 gap-2">
          {audio.se.library.map((se) => (
            <button
              key={se.id}
              className="flex flex-col items-center justify-center p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-accent transition-colors"
            >
              <span className="text-2xl">{se.icon}</span>
              <span className="text-xs mt-1 text-muted-foreground">{se.name}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
