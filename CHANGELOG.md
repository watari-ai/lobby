# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-02-19

### Added
- **`lobby init`** - Project scaffolding command (config, sample script, directory structure)
- **`lobby export`** - YouTube-ready packaging (video + subtitles + metadata.json + description.txt)
- **`lobby validate`** - Script preview & validation (emotion distribution, estimated duration, warnings)
- **`lobby doctor`** - Environment diagnostics (Python, ffmpeg, TTS, frontend dependencies)
- **Docker support** - Dockerfile + docker-compose.yml
- **Unified config loader** - `--config` flag for record/record-video commands
- **BGM mixing** - Auto-ducking support during speech
- **TTS retry** - Exponential backoff for transient errors
- **Accurate audio duration** - ffprobe-based measurement

### Fixed
- Lint errors (ruff auto-fix)
- Audio duration estimation (byte-based → ffprobe)
- API route prefix consistency

### Changed
- Test suite expanded: 252 → 407 tests
- README test badge updated

## [1.0.0] - 2026-02-13

### Added

#### Core Features
- **Recording Mode** - Script-based video production with emotion tags
- **Live Mode** - Real-time streaming with YouTube/Twitch integration
- **Dialogue Mode** - Interactive conversation with microphone input

#### Emotion Engine
- Rule-based emotion analysis (keywords, emoji, punctuation patterns)
- LLM-based emotion tagging via OpenClaw
- Emotion-to-TTS instruction mapping
- Emotion-to-Avatar expression/gesture mapping

#### TTS Integration
- Qwen3-TTS support (recommended, high-quality, local)
- MeloTTS support (lightweight, fast)
- VOICEVOX support (Japanese-optimized)
- ElevenLabs support (cloud)
- Edge TTS support (free)
- Custom OpenAI-compatible API support

#### Avatar System
- **2D Support**
  - Live2D (.moc3) rendering with PixiJS
  - PNG sprite-based avatars
  - 6 expression presets (neutral, happy, sad, angry, surprised, thinking)
  - Physics simulation (eye blink, breathing, gravity, wind)
  - WebSocket-based real-time parameter streaming
- **3D Support**
  - VRM model support with Three.js
  - Basic pose and expression control

#### Live Streaming
- OpenClaw Gateway native integration
- YouTube Live chat integration
- Twitch IRC and EventSub integration
- OBS WebSocket integration
- Real-time comment queue management
- Super Chat / donation reactions

#### Subtitle System
- SRT/VTT export for recording mode
- Real-time subtitle display for live mode
- Multi-language translation support
- Customizable font, position, and background

#### Archive Features
- Automatic highlight detection (audio peaks, emotions, chat activity, keywords)
- Clip extraction with customizable duration
- Thumbnail auto-generation (YouTube/Twitter/Square formats)
- Quality analysis for thumbnail selection

#### Web UI
- React + Vite + Tailwind CSS 3.4
- Zustand state management
- Real-time Live2D preview with 60fps animation
- Camera control panel (presets, zoom, offset, transitions)
- Background panel (image/video/color)
- Subtitle settings panel
- Audio panel (BGM player, SE)
- Effects panel (particles, filters)

#### Desktop Application
- Electron 33 integration
- Cross-platform support (macOS, Windows, Linux)
- Overlay mode (always-on-top with adjustable transparency)
- Auto-update via GitHub Releases
- Native window controls

#### Scene Management
- Background switching
- Camera angle presets (close-up, wide)
- Overlay support (text, effects)

#### Audio Management
- BGM playlist with crossfade
- Sound effect triggers
- Auto-ducking during speech

#### Developer Experience
- FastAPI backend with WebSocket + REST API
- Comprehensive test suite (252 tests)
- GitHub Actions CI/CD
- Dependabot security updates
- API Reference documentation
- Tutorial documentation

### Technical Details
- **Backend:** Python 3.11+, FastAPI, asyncio
- **Frontend:** Electron + React, PixiJS 7, Three.js, Zustand
- **Build:** Vite 5, electron-builder
- **Package Manager:** pnpm

---

## Development History

### Phase 7: Desktop Application (2026-02-12)
- Electron integration
- Auto-update functionality
- Live2D motion playback via WebSocket
- Frontend build optimization

### Phase 6: Web UI (2026-02-12)
- Tailwind CSS dark theme
- Control panels (camera, background, subtitle, audio, effects)
- WebSocket API integration
- Real-time Live2D preview sync

### Phase 5: Subtitle & Archive (2026-02-11)
- SRT/VTT generation
- Translation subtitle support
- Highlight detection algorithm
- Clip extraction and thumbnail generation

### Phase 4: Extended Features (2026-02-11)
- VRM 3D avatar support
- Twitch integration
- BGM/SE management
- Scene management

### Phase 3: Live Streaming (2026-02-11)
- OpenClaw Gateway client
- YouTube Live integration
- OBS WebSocket integration

### Phase 2: Live2D (2026-02-11)
- Live2D parameter generation
- Expression presets
- Physics simulation

### Phase 1: MVP (2026-02-11)
- Project initialization
- Recording mode implementation
- Qwen3-TTS integration
- Basic lipsync

[Unreleased]: https://github.com/watari-ai/lobby/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/watari-ai/lobby/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/watari-ai/lobby/releases/tag/v1.0.0
