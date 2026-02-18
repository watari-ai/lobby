// Camera types
export type CameraPreset = "full" | "bust" | "shoulder" | "close" | "custom";
export type CameraTransition = "cut" | "smooth" | "zoom";

export interface CameraState {
  preset: CameraPreset;
  zoom: number;
  offsetX: number;
  offsetY: number;
  transition: CameraTransition;
  transitionDuration: number;
}

// Background types
export type BackgroundType = "image" | "video" | "color";

export interface BackgroundPreset {
  id: string;
  name: string;
  type: BackgroundType;
  source: string;
  thumbnail?: string;
}

export interface BackgroundState {
  type: BackgroundType;
  source: string;
  presets: BackgroundPreset[];
}

// Subtitle types
export interface FontConfig {
  family: string;
  size: number;
  color: string;
  weight: number;
}

export interface PositionConfig {
  vertical: "top" | "middle" | "bottom";
  horizontal: "left" | "center" | "right";
  marginX: number;
  marginY: number;
}

export interface BackgroundConfig {
  color: string;
  opacity: number;
  padding: number;
}

export interface OutlineConfig {
  color: string;
  width: number;
}

export interface ShadowConfig {
  color: string;
  blur: number;
  offsetX: number;
  offsetY: number;
}

export interface SubtitleState {
  enabled: boolean;
  font: FontConfig;
  position: PositionConfig;
  background: BackgroundConfig;
  outline?: OutlineConfig;
  shadow?: ShadowConfig;
  currentText: string;
}

// Audio types
export interface AudioTrack {
  id: string;
  name: string;
  duration: number;
  path: string;
}

export interface SoundEffect {
  id: string;
  name: string;
  icon: string;
  category: string;
  path: string;
}

export interface AudioState {
  bgm: {
    playing: boolean;
    currentTrack: AudioTrack | null;
    volume: number;
    progress: number;
    playlist: AudioTrack[];
  };
  se: {
    library: SoundEffect[];
    volume: number;
  };
}

// Effect types
export type EffectType = "confetti" | "fireworks" | "hearts" | "stars" | "snow" | "rain" | "flash" | "shake";
export type FilterType = "none" | "blur" | "vignette";

export interface ActiveEffect {
  id: string;
  type: EffectType;
  intensity: number;
  startedAt: number;
}

export interface EffectState {
  activeEffects: ActiveEffect[];
  filter: FilterType;
}

// Expression types
export const EXPRESSIONS = ['neutral', 'happy', 'sad', 'excited', 'surprised', 'angry', 'thinking'] as const;
export type Expression = typeof EXPRESSIONS[number];

// Physics types
export interface PhysicsConfig {
  enabled: boolean;
  gravity: { x: number; y: number };
  wind: { x: number; y: number };
}

// Live2D params
export interface Live2DParams {
  ParamMouthOpenY: number;
  ParamEyeLOpen: number;
  ParamEyeROpen: number;
  ParamEyeBallX: number;
  ParamEyeBallY: number;
  ParamBodyAngleX: number;
  ParamBodyAngleY: number;
  ParamBreath: number;
  [key: string]: number;
}
