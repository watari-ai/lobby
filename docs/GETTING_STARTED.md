# 🚀 Getting Started with Lobby

このガイドでは、Lobbyをインストールして最初の収録を行うまでの手順を説明します。

## 📋 前提条件

以下がインストールされていることを確認してください：

| 要件 | バージョン | 確認コマンド |
|------|-----------|-------------|
| Python | 3.11以上 | `python --version` |
| Node.js | 20以上 | `node --version` |
| pnpm | 8以上 | `pnpm --version` |
| FFmpeg | 最新推奨 | `ffmpeg -version` |

### インストール（未インストールの場合）

```bash
# macOS
brew install python@3.11 node pnpm ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install python3.11 python3.11-venv nodejs npm ffmpeg
npm install -g pnpm
```

## 📦 インストール

### 1. リポジトリをクローン

```bash
git clone https://github.com/watari-ai/lobby.git
cd lobby
```

### 2. バックエンドセットアップ

```bash
# 仮想環境を作成（推奨）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係をインストール
pip install -e .
```

### 3. フロントエンドセットアップ

```bash
cd frontend
pnpm install
cd ..
```

## ⚙️ 初期設定

### 1. 設定ファイルを作成

```bash
cp config/lobby.example.yaml config/lobby.yaml
```

### 2. 設定を編集

```yaml
# config/lobby.yaml

# TTS設定（必須）
tts:
  provider: "qwen3-tts"  # または edge-tts（無料）, elevenlabs など
  base_url: "http://localhost:8880/v1"
  voice: "ono_anna"

# 出力設定
output:
  directory: "./output"
  format: "mp4"
  resolution: "1920x1080"
  fps: 30

# アバター設定（オプション）
avatar:
  type: "png"  # png, live2d, vrm
  model: "./models/default.png"
```

### TTS別の設定例

#### Qwen3-TTS（高品質・ローカル）
```yaml
tts:
  provider: "qwen3-tts"
  base_url: "http://localhost:8880/v1"
  voice: "ono_anna"
```

#### Edge TTS（無料・クラウド）
```yaml
tts:
  provider: "edge-tts"
  voice: "ja-JP-NanamiNeural"
```

#### ElevenLabs（高品質・クラウド）
```yaml
tts:
  provider: "elevenlabs"
  api_key: "your-api-key"
  voice: "your-voice-id"
```

## 🎬 最初の収録

### 1. 台本を作成

```bash
mkdir -p scripts
cat > scripts/hello.txt << 'EOF'
[happy] こんにちは！
[excited] 初めての収録、ワクワクするね！
[neutral] これからよろしくお願いします。
EOF
```

### 2. APIサーバーを起動

```bash
# ターミナル1: バックエンドサーバー
source .venv/bin/activate
python -m backend.main --port 8100
```

### 3. 収録を実行

```bash
# ターミナル2: 収録コマンド
curl -X POST http://localhost:8100/api/recording/start \
  -H "Content-Type: application/json" \
  -d '{
    "script_path": "scripts/hello.txt",
    "output_path": "output/hello.mp4"
  }'
```

または、Web UIを使用：

```bash
# ターミナル2: フロントエンド開発サーバー
cd frontend
pnpm run dev
# ブラウザで http://localhost:5173 を開く
```

### 4. 出力を確認

収録が完了すると、`output/hello.mp4` に動画が生成されます。

## 🖥️ デスクトップアプリ

Electronベースのデスクトップアプリとしても使用できます：

```bash
cd frontend

# 開発モード
pnpm run electron:dev

# ビルド（配布用）
pnpm run electron:build
```

## 🔧 トラブルシューティング

### TTS接続エラー

```
Error: Connection refused to TTS server
```

**解決策:**
1. TTSサーバーが起動しているか確認
2. `config/lobby.yaml` の `tts.base_url` が正しいか確認
3. ファイアウォールがポートをブロックしていないか確認

### FFmpegが見つからない

```
Error: FFmpeg not found
```

**解決策:**
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg

# パスが通っているか確認
which ffmpeg
```

### Live2Dモデルが読み込めない

```
Error: Failed to load Live2D model
```

**解決策:**
1. モデルファイル（.moc3）のパスが正しいか確認
2. テクスチャファイルが同じディレクトリにあるか確認
3. `model.json` または `model3.json` が存在するか確認

### メモリ不足

大きなモデルや長時間の収録でメモリ不足が発生する場合：

```yaml
# config/lobby.yaml
performance:
  max_memory_mb: 4096
  chunk_size: 60  # 60秒ごとに分割処理
```

## 📚 次のステップ

- [チュートリアル](TUTORIAL.md) - より詳細な使い方
- [API リファレンス](API_REFERENCE.md) - REST/WebSocket API
- [設計書](DESIGN.md) - アーキテクチャ詳細

## 💬 サポート

- **Issues:** [GitHub Issues](https://github.com/watari-ai/lobby/issues)
- **Discord:** [OpenClaw Community](https://discord.com/invite/clawd)

---

*Lobby v1.0.0 | MIT License*
