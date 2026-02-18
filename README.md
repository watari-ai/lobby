# 🦞 Lobby - AI VTuber配信・収録ソフト

<p align="center">
  <img src="docs/lobby-logo.png" alt="Lobby Logo" width="200">
</p>

<p align="center">
  <strong>OpenClawネイティブ連携のAI VTuber配信・収録ソフトウェア</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Documentation</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0--rc-blue" alt="Version">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/tests-322%20passed-green" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## 🎯 概要

**Lobby**は、[OpenClaw](https://github.com/openclaw/openclaw)と連携するオープンソースのAI VTuber配信・収録ソフトウェアです。

台本収録からライブ配信まで、AI VTuberに必要な機能をすべて統合。感情エンジンによる自然なリアクションで、魅力的なコンテンツ制作をサポートします。

## ✨ Features

### 🎬 3つのモード

| モード | 用途 | 説明 |
|--------|------|------|
| **収録モード** | 動画制作 | 台本ファイルに沿って収録。感情タグで表現を制御 |
| **ライブモード** | 生配信 | YouTube/Twitchコメントにリアルタイム反応 |
| **対話モード** | テスト/雑談 | マイク入力でインタラクティブ会話 |

### 🤖 OpenClaw連携

- OpenClaw Gatewayとネイティブ連携
- AI人格・記憶を維持したまま配信
- セッション永続化対応

### 💭 感情エンジン

- テキストから感情を自動分析
- TTS指示を動的に生成（「嬉しそうに」「悲しげに」等）
- アバターの表情・ジェスチャーを連動制御

### 🎤 TTS統合

複数のTTSエンジンに対応：
- Qwen3-TTS（推奨、高品質、ローカル）
- MeloTTS（軽量、高速）
- VOICEVOX（日本語特化）
- ElevenLabs（クラウド）
- Edge TTS（無料）

### 🎭 アバター対応

- **2D:** Live2D (.moc3), PNG立ち絵
- **3D:** VRM, VRoid
- リップシンク（音声波形/フォネーム連動）
- 表情・ポーズ・ジェスチャー制御

### 📺 配信統合

- YouTube Live / Twitch対応
- コメント取得・フィルタリング
- スパチャ/投げ銭反応
- OBS連携（NDI/仮想カメラ）

## 🚀 Installation

```bash
# Clone repository
git clone https://github.com/watari-ai/lobby.git
cd lobby

# Install dependencies
pip install -e .

# Run
lobby --config config/lobby.yaml
```

## ⚡ Quick Start

### 1. 設定ファイル作成

```yaml
# config/lobby.yaml
openclaw:
  gateway_url: "http://localhost:18790/v1"
  api_key: "your-gateway-token"
  user: "lobby-session"

tts:
  provider: "qwen3-tts"
  base_url: "http://localhost:8880/v1"
  voice: "ono_anna"

avatar:
  type: "live2d"
  model_path: "models/your-model.moc3"
```

### 2. 収録モードで台本読み上げ

```bash
lobby record --script scripts/intro.txt --output video/intro.mp4
```

### 3. ライブモードで配信

```bash
lobby live --youtube --channel-id YOUR_CHANNEL_ID
```

## 📖 Documentation

- [設計書](docs/DESIGN.md) - アーキテクチャと機能詳細
- [チュートリアル](docs/TUTORIAL.md) - ステップバイステップ導入ガイド
- [APIリファレンス](docs/API_REFERENCE.md) - REST/WebSocket API仕様
- [Web UI設計](docs/WEB_UI_DESIGN.md) - フロントエンド構成

## 🏗️ アーキテクチャ

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Input     │────▶│   Emotion    │────▶│    TTS      │
│ (台本/Chat) │     │   Engine     │     │   Engine    │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                     │
                           ▼                     ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   Avatar     │◀────│   Audio     │
                    │   Engine     │     │  (Lipsync)  │
                    └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Output     │
                    │ (OBS/Video)  │
                    └──────────────┘
```

## 🤝 Contributing

コントリビューション歓迎！詳細は[CONTRIBUTING.md](CONTRIBUTING.md)をご覧ください。

## 📄 License

MIT License - 詳細は[LICENSE](LICENSE)をご覧ください。

## 🙏 Credits

- [OpenClaw](https://github.com/openclaw/openclaw) - AI Agent Framework
- [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) - インスピレーション

---

<p align="center">
  Made with 🦞 by the Lobby Team
</p>
