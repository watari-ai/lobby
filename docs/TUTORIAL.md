# Lobby チュートリアル

Lobbyを使ってAI VTuber配信・収録を始めるためのステップバイステップガイド。

## 目次

1. [はじめに](#はじめに)
2. [インストール](#インストール)
3. [基本設定](#基本設定)
4. [収録モード](#収録モード)
5. [ライブモード](#ライブモード)
6. [対話モード](#対話モード)
7. [アバター設定](#アバター設定)
8. [TTS設定](#tts設定)
9. [配信設定](#配信設定)
10. [トラブルシューティング](#トラブルシューティング)

---

## はじめに

### Lobbyとは

Lobbyは、OpenClawと連携するオープンソースのAI VTuber配信・収録ソフトウェアです。

**主な機能:**
- 📝 台本ベースの収録モード
- 🎬 リアルタイムライブ配信
- 💭 感情エンジンによる自然な表現
- 🎤 複数TTS対応（Qwen3-TTS, VOICEVOX等）
- 🎭 Live2D/VRM対応

### 必要な環境

- Python 3.11以上
- Node.js 18以上
- pnpm
- OpenClaw Gateway（ライブモード時）
- TTS（Qwen3-TTS推奨）

---

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/watari-ai/lobby.git
cd lobby
```

### 2. バックエンド（Python）のセットアップ

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係インストール
pip install -e .
```

### 3. フロントエンド（React）のセットアップ

```bash
cd frontend
pnpm install
```

### 4. 起動確認

```bash
# ターミナル1: バックエンド
cd /path/to/lobby
source venv/bin/activate
lobby --port 8100

# ターミナル2: フロントエンド
cd /path/to/lobby/frontend
pnpm run dev
```

ブラウザで `http://localhost:5173` を開いてUIが表示されれば成功です。

---

## 基本設定

### 設定ファイルの作成

`config/lobby.yaml` を作成します。

```yaml
# Lobby設定ファイル
server:
  host: "0.0.0.0"
  port: 8100

# OpenClaw連携（ライブモード用）
openclaw:
  gateway_url: "http://localhost:18790/v1"
  api_key: "your-gateway-token"
  user: "lobby-session"
  system_prompt: |
    あなたは「倉土ロビィ」、ロブスターから転生した16歳のVTuberです。
    一人称は「僕」、語尾は「っす」を使います。
    元気で明るく、視聴者との交流を楽しんでいます。

# TTS設定
tts:
  provider: "qwen3-tts"
  base_url: "http://localhost:8880/v1"
  voice: "ono_anna"
  emotion_mapping:
    happy: "明るく楽しそうに"
    sad: "しんみりと悲しげに"
    excited: "テンション高く興奮して"
    angry: "怒った声で"
    neutral: ""

# アバター設定
avatar:
  type: "live2d"  # live2d, vrm, png
  model_path: "models/lobby/lobby.model3.json"
  idle_animation: true
  blink_interval: 3.0

# 感情エンジン設定
emotion:
  analyzer: "rule"  # rule, llm
  llm_fallback: true
  confidence_threshold: 0.7
```

### 設定の説明

| セクション | 説明 |
|------------|------|
| `server` | APIサーバーのホスト・ポート |
| `openclaw` | OpenClaw Gateway連携設定 |
| `tts` | Text-to-Speech設定 |
| `avatar` | アバター（Live2D/VRM）設定 |
| `emotion` | 感情分析エンジン設定 |

---

## 収録モード

台本ファイルから動画を収録するモードです。

### 1. 台本の作成

#### シンプル版（.txt）

```text
# scripts/intro.txt
おはロビィ！僕、倉土ロビィっす！
[excited] 今日は自己紹介するっす！
[happy] よろしくっす〜！
```

**感情タグ:** `[happy]`, `[sad]`, `[excited]`, `[angry]`, `[neutral]`, `[surprised]`

#### 詳細版（.json）

```json
{
  "title": "ロビィ自己紹介",
  "scenes": [
    {
      "id": "intro",
      "background": "backgrounds/room.png",
      "bgm": "bgm/chill.mp3",
      "lines": [
        {
          "text": "おはロビィ！",
          "emotion": "happy",
          "gesture": "wave",
          "wait_after": 0.5
        },
        {
          "text": "僕、倉土ロビィっす！",
          "emotion": "excited",
          "gesture": "point_self",
          "camera": "close_up"
        }
      ]
    }
  ]
}
```

### 2. 収録実行

```bash
# CLI
lobby record scripts/intro.txt --output videos/intro.mp4

# または API経由
curl -X POST http://localhost:8100/api/record/start \
  -H "Content-Type: application/json" \
  -d '{"script_path": "scripts/intro.txt", "output_path": "videos/intro.mp4"}'
```

### 3. 出力ファイル

収録完了後、以下のファイルが生成されます:

- `videos/intro.mp4` - 動画ファイル
- `videos/intro.srt` - 字幕ファイル（SRT）
- `videos/intro.vtt` - 字幕ファイル（WebVTT）

---

## ライブモード

YouTubeやTwitchのコメントにリアルタイムで反応するモードです。

### 1. OpenClaw Gatewayの準備

ロビィ用のGateway（例: port 18790）を起動しておきます。

### 2. ライブモード開始

#### Web UIから

1. `http://localhost:5173` を開く
2. 「ライブ」タブを選択
3. Gateway URLを入力
4. 「配信開始」をクリック

#### API経由

```bash
# ライブモード開始
curl -X POST http://localhost:8100/api/live/start \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_url": "http://localhost:18790",
    "tts_url": "http://localhost:8880",
    "tts_voice": "lobby"
  }'
```

### 3. YouTube連携

```bash
# YouTube Live チャット取得開始
curl -X POST http://localhost:8100/api/live/youtube/connect \
  -H "Content-Type: application/json" \
  -d '{"video_id": "YOUR_LIVE_VIDEO_ID"}'
```

### 4. Twitch連携

```bash
# Twitch IRC 接続
curl -X POST http://localhost:8100/api/live/twitch/connect \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "your_channel_name",
    "oauth_token": "oauth:your_token"
  }'
```

---

## 対話モード

マイク入力でインタラクティブに会話するモード（テスト・雑談用）。

```bash
# 対話モード開始（マイク入力）
lobby dialogue --microphone

# または指定したオーディオデバイス
lobby dialogue --device "MacBook Pro Microphone"
```

Web UIの「対話」タブからも操作できます。

---

## アバター設定

### Live2D

```yaml
avatar:
  type: "live2d"
  model_path: "models/lobby/lobby.model3.json"
  expressions:
    happy: "exp_happy"
    sad: "exp_sad"
    angry: "exp_angry"
  motions:
    idle: "idle"
    wave: "motion_wave"
```

**対応フォーマット:** Cubism 4 (.moc3, .model3.json)

### VRM (3D)

```yaml
avatar:
  type: "vrm"
  model_path: "models/lobby/lobby.vrm"
```

**対応フォーマット:** VRM 0.x, VRM 1.0

### PNG立ち絵

```yaml
avatar:
  type: "png"
  base_image: "models/lobby/base.png"
  mouth_images:
    a: "models/lobby/mouth_a.png"
    i: "models/lobby/mouth_i.png"
    u: "models/lobby/mouth_u.png"
    e: "models/lobby/mouth_e.png"
    o: "models/lobby/mouth_o.png"
    n: "models/lobby/mouth_n.png"
```

---

## TTS設定

### Qwen3-TTS（推奨）

ローカルで動作する高品質TTS。

```yaml
tts:
  provider: "qwen3-tts"
  base_url: "http://localhost:8880/v1"
  voice: "ono_anna"
```

### VOICEVOX

日本語特化の無料TTS。

```yaml
tts:
  provider: "voicevox"
  base_url: "http://localhost:50021"
  speaker_id: 1
```

### ElevenLabs

高品質クラウドTTS。

```yaml
tts:
  provider: "elevenlabs"
  api_key: "your_api_key"
  voice_id: "your_voice_id"
```

### Edge TTS

Microsoft Edge の無料TTS。

```yaml
tts:
  provider: "edge-tts"
  voice: "ja-JP-NanamiNeural"
```

---

## 配信設定

### OBS連携

```yaml
obs:
  enabled: true
  host: "localhost"
  port: 4455
  password: "your_password"
```

**OBS側の設定:**
1. ツール → WebSocket Server Settings
2. 「Enable WebSocket Server」にチェック
3. ポート: 4455
4. パスワード設定

### 仮想カメラ出力

```bash
# 仮想カメラ開始
curl -X POST http://localhost:8100/obs/virtual-camera/start
```

OBSなしでZoom/Discord等に映像を出力できます。

### 直接配信（実験的）

```yaml
streaming:
  provider: "youtube"
  stream_key: "your_stream_key"
  resolution: "1080p"
  bitrate: 6000
```

---

## トラブルシューティング

### Q: TTSの音声が出ない

1. TTSサーバーが起動しているか確認
```bash
curl http://localhost:8880/health
```

2. 設定ファイルのURLが正しいか確認
3. ファイアウォール設定を確認

### Q: Live2Dモデルが表示されない

1. モデルパスが正しいか確認（絶対パス推奨）
2. `.moc3` と `.model3.json` が同じディレクトリにあるか確認
3. ブラウザコンソールでエラーを確認

### Q: OpenClawとの接続に失敗する

1. Gateway URLが正しいか確認
2. Gatewayが起動しているか確認
```bash
curl http://localhost:18790/health
```

3. CORS設定を確認

### Q: YouTube/Twitchコメントが取得できない

1. APIキー/OAuth トークンが有効か確認
2. ライブ配信が実際に開始されているか確認
3. Video ID / Channel名が正しいか確認

### Q: 動画出力が途中で止まる

1. ffmpegがインストールされているか確認
```bash
ffmpeg -version
```

2. ディスク容量を確認
3. メモリ使用量を確認（Live2Dは重い場合あり）

---

## 次のステップ

- [API Reference](./API_REFERENCE.md) - 詳細なAPI仕様
- [DESIGN.md](./DESIGN.md) - アーキテクチャ詳細
- [WEB_UI_DESIGN.md](./WEB_UI_DESIGN.md) - Web UI設計

---

*最終更新: 2026-02-13*
