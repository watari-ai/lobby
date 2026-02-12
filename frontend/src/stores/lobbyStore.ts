import { create } from 'zustand';
import type {
  CameraState,
  CameraPreset,
  BackgroundState,
  BackgroundType,
  SubtitleState,
  AudioState,
  AudioTrack,
  EffectState,
  EffectType,
  FilterType,
  Expression,
  PhysicsConfig,
  Live2DParams,
} from '../types';

interface LobbyStore {
  // Connection
  connected: boolean;
  backendUrl: string;
  setConnected: (connected: boolean) => void;

  // Camera
  camera: CameraState;
  setCameraPreset: (preset: CameraPreset) => void;
  setCameraZoom: (zoom: number) => void;
  setCameraOffset: (x: number, y: number) => void;
  setCameraTransition: (transition: CameraState['transition'], duration?: number) => void;

  // Background
  background: BackgroundState;
  setBackgroundType: (type: BackgroundType) => void;
  setBackgroundSource: (source: string) => void;

  // Subtitle
  subtitle: SubtitleState;
  setSubtitleEnabled: (enabled: boolean) => void;
  setSubtitleText: (text: string) => void;
  setSubtitleFont: (font: Partial<SubtitleState['font']>) => void;
  setSubtitlePosition: (position: Partial<SubtitleState['position']>) => void;
  setSubtitleBackground: (bg: Partial<SubtitleState['background']>) => void;

  // Audio
  audio: AudioState;
  setBgmPlaying: (playing: boolean) => void;
  setBgmTrack: (track: AudioTrack | null) => void;
  setBgmVolume: (volume: number) => void;
  setBgmProgress: (progress: number) => void;
  setSeVolume: (volume: number) => void;

  // Effects
  effects: EffectState;
  triggerEffect: (type: EffectType, intensity?: number) => void;
  stopEffect: (id?: string) => void;
  setFilter: (filter: FilterType) => void;

  // Expression
  expression: Expression;
  setExpression: (expression: Expression) => void;

  // Motion
  currentMotion: string | null;
  setMotion: (motion: string | null) => void;

  // Physics
  physics: PhysicsConfig;
  setPhysics: (config: Partial<PhysicsConfig>) => void;

  // Live2D Params
  live2dParams: Live2DParams;
  setLive2DParams: (params: Partial<Live2DParams>) => void;
}

export const useLobbyStore = create<LobbyStore>((set) => ({
  // Connection
  connected: false,
  backendUrl: 'ws://localhost:8000',
  setConnected: (connected) => set({ connected }),

  // Camera - Default: full body view
  camera: {
    preset: 'full',
    zoom: 1.0,
    offsetX: 0,
    offsetY: 0,
    transition: 'smooth',
    transitionDuration: 500,
  },
  setCameraPreset: (preset) => {
    const zoomMap: Record<CameraPreset, number> = {
      full: 1.0,
      bust: 1.5,
      shoulder: 2.0,
      close: 2.5,
      custom: 1.0,
    };
    set((state) => ({
      camera: {
        ...state.camera,
        preset,
        zoom: preset !== 'custom' ? zoomMap[preset] : state.camera.zoom,
      },
    }));
  },
  setCameraZoom: (zoom) =>
    set((state) => ({
      camera: { ...state.camera, zoom, preset: 'custom' },
    })),
  setCameraOffset: (offsetX, offsetY) =>
    set((state) => ({
      camera: { ...state.camera, offsetX, offsetY, preset: 'custom' },
    })),
  setCameraTransition: (transition, duration) =>
    set((state) => ({
      camera: {
        ...state.camera,
        transition,
        transitionDuration: duration ?? state.camera.transitionDuration,
      },
    })),

  // Background
  background: {
    type: 'color',
    source: '#1a1a2e',
    presets: [
      { id: 'room', name: 'Room', type: 'image', source: '/backgrounds/room.jpg' },
      { id: 'city', name: 'City', type: 'image', source: '/backgrounds/city.jpg' },
      { id: 'park', name: 'Park', type: 'image', source: '/backgrounds/park.jpg' },
      { id: 'game', name: 'Game', type: 'image', source: '/backgrounds/game.jpg' },
    ],
  },
  setBackgroundType: (type) =>
    set((state) => ({ background: { ...state.background, type } })),
  setBackgroundSource: (source) =>
    set((state) => ({ background: { ...state.background, source } })),

  // Subtitle
  subtitle: {
    enabled: true,
    font: {
      family: 'Noto Sans JP',
      size: 32,
      color: '#ffffff',
      weight: 400,
    },
    position: {
      vertical: 'bottom',
      horizontal: 'center',
      marginX: 0,
      marginY: 40,
    },
    background: {
      color: '#000000',
      opacity: 0.7,
      padding: 12,
    },
    currentText: '',
  },
  setSubtitleEnabled: (enabled) =>
    set((state) => ({ subtitle: { ...state.subtitle, enabled } })),
  setSubtitleText: (currentText) =>
    set((state) => ({ subtitle: { ...state.subtitle, currentText } })),
  setSubtitleFont: (font) =>
    set((state) => ({
      subtitle: { ...state.subtitle, font: { ...state.subtitle.font, ...font } },
    })),
  setSubtitlePosition: (position) =>
    set((state) => ({
      subtitle: {
        ...state.subtitle,
        position: { ...state.subtitle.position, ...position },
      },
    })),
  setSubtitleBackground: (bg) =>
    set((state) => ({
      subtitle: {
        ...state.subtitle,
        background: { ...state.subtitle.background, ...bg },
      },
    })),

  // Audio
  audio: {
    bgm: {
      playing: false,
      currentTrack: null,
      volume: 0.5,
      progress: 0,
      playlist: [],
    },
    se: {
      library: [
        { id: 'clap', name: 'Clap', icon: '👏', category: 'reaction', path: '/se/clap.mp3' },
        { id: 'yay', name: 'Yay', icon: '🎉', category: 'reaction', path: '/se/yay.mp3' },
        { id: 'lol', name: 'LOL', icon: '😂', category: 'reaction', path: '/se/lol.mp3' },
        { id: 'love', name: 'Love', icon: '💖', category: 'reaction', path: '/se/love.mp3' },
      ],
      volume: 0.7,
    },
  },
  setBgmPlaying: (playing) =>
    set((state) => ({
      audio: { ...state.audio, bgm: { ...state.audio.bgm, playing } },
    })),
  setBgmTrack: (currentTrack) =>
    set((state) => ({
      audio: { ...state.audio, bgm: { ...state.audio.bgm, currentTrack } },
    })),
  setBgmVolume: (volume) =>
    set((state) => ({
      audio: { ...state.audio, bgm: { ...state.audio.bgm, volume } },
    })),
  setBgmProgress: (progress) =>
    set((state) => ({
      audio: { ...state.audio, bgm: { ...state.audio.bgm, progress } },
    })),
  setSeVolume: (volume) =>
    set((state) => ({
      audio: { ...state.audio, se: { ...state.audio.se, volume } },
    })),

  // Effects
  effects: {
    activeEffects: [],
    filter: 'none',
  },
  triggerEffect: (type, intensity = 1.0) =>
    set((state) => ({
      effects: {
        ...state.effects,
        activeEffects: [
          ...state.effects.activeEffects,
          { id: `${type}-${Date.now()}`, type, intensity, startedAt: Date.now() },
        ],
      },
    })),
  stopEffect: (id) =>
    set((state) => ({
      effects: {
        ...state.effects,
        activeEffects: id
          ? state.effects.activeEffects.filter((e) => e.id !== id)
          : [],
      },
    })),
  setFilter: (filter) =>
    set((state) => ({ effects: { ...state.effects, filter } })),

  // Expression
  expression: 'neutral',
  setExpression: (expression) => set({ expression }),

  // Motion
  currentMotion: null,
  setMotion: (currentMotion) => set({ currentMotion }),

  // Physics
  physics: {
    enabled: true,
    gravity: { x: 0, y: -1 },
    wind: { x: 0, y: 0 },
  },
  setPhysics: (config) =>
    set((state) => ({ physics: { ...state.physics, ...config } })),

  // Live2D Params
  live2dParams: {
    ParamMouthOpenY: 0,
    ParamEyeLOpen: 1,
    ParamEyeROpen: 1,
    ParamEyeBallX: 0,
    ParamEyeBallY: 0,
    ParamBodyAngleX: 0,
    ParamBodyAngleY: 0,
    ParamBreath: 0,
  },
  setLive2DParams: (params) =>
    set((state) => ({ live2dParams: { ...state.live2dParams, ...params } })),
}));
