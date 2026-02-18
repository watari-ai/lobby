import React from 'react';
import {
  Camera,
  Image,
  MessageSquare,
  Music,
  Sparkles,
  Settings,
  MessageCircle,
  Video,
} from 'lucide-react';
import { cn } from '../../lib/utils';

export type PanelType = 'camera' | 'background' | 'subtitle' | 'audio' | 'effects' | 'chat' | 'recording' | 'settings';

interface SidebarProps {
  activePanel: PanelType;
  onPanelChange: (panel: PanelType) => void;
}

const PANELS: { id: PanelType; icon: React.ReactNode; label: string }[] = [
  { id: 'camera', icon: <Camera className="w-5 h-5" />, label: 'Camera' },
  { id: 'background', icon: <Image className="w-5 h-5" />, label: 'Background' },
  { id: 'subtitle', icon: <MessageSquare className="w-5 h-5" />, label: 'Subtitle' },
  { id: 'audio', icon: <Music className="w-5 h-5" />, label: 'Audio' },
  { id: 'effects', icon: <Sparkles className="w-5 h-5" />, label: 'Effects' },
  { id: 'chat', icon: <MessageCircle className="w-5 h-5" />, label: 'Chat' },
  { id: 'recording', icon: <Video className="w-5 h-5" />, label: 'Record' },
  { id: 'settings', icon: <Settings className="w-5 h-5" />, label: 'Settings' },
];

export function Sidebar({ activePanel, onPanelChange }: SidebarProps) {
  return (
    <aside className="w-16 border-r border-border bg-background flex flex-col items-center py-4 gap-2">
      {PANELS.map((panel) => (
        <button
          key={panel.id}
          onClick={() => onPanelChange(panel.id)}
          className={cn(
            "w-12 h-12 rounded-lg flex flex-col items-center justify-center gap-1 transition-colors",
            activePanel === panel.id
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
          )}
          title={panel.label}
        >
          {panel.icon}
          <span className="text-[10px]">{panel.label}</span>
        </button>
      ))}
    </aside>
  );
}
