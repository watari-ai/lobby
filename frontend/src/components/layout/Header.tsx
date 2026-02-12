import React from 'react';
import { Wifi, WifiOff } from 'lucide-react';
import { useLobbyStore } from '../../stores/lobbyStore';
import { cn } from '../../lib/utils';

export function Header() {
  const connected = useLobbyStore((state) => state.connected);

  return (
    <header className="h-14 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-4">
      <div className="flex items-center gap-3">
        <span className="text-2xl">🦞</span>
        <h1 className="text-xl font-semibold text-foreground">Lobby</h1>
        <span className="text-xs text-muted-foreground">Control Panel</span>
      </div>
      
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-full text-sm",
            connected
              ? "bg-green-500/10 text-green-500"
              : "bg-red-500/10 text-red-500"
          )}
        >
          {connected ? (
            <>
              <Wifi className="w-4 h-4" />
              <span>Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4" />
              <span>Disconnected</span>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
