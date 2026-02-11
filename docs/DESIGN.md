# Lobby - AI VTuber配信ソフト 設計書

## 概要

**Lobby**は、OpenClawと連携するオープンソースのAI VTuber配信・収録ソフトウェア。
ロビィ（倉土ロビィ）のデビューに合わせて開発し、他のOpenClawユーザーも使えるツールとして公開。

## コア機能

### 1. モード切り替え

| モード | 用途 | 入力ソース |
|--------|------|-----------|
| **収録モード** | 動画制作 | 台本ファイル（.txt, .md, .json） |
| **ライブモード** | 生配信 | OpenClaw Gateway + YouTube/Twitchコメント |
| **対話モード** | テスト/雑談 | マイク入力（ASR） |

### 2. OpenClaw連携

```
[YouTube/Twitchコメント] ──┐
                          ├──▶ [OpenClaw Gateway] ──▶ [応答テキスト]
[マイク入力(ASR)] ────────┘                              │
                                                        ▼
[台本ファイル] ────────────────────────────────────▶ [感情エンジン]
                                                        │
                                                        ▼
                                                    [TTS Engine]
                                                        │
                                                        ▼
                                                [Audio + Phonemes]
                                                        │
                                                        ▼
                                            [Avatar Engine (2D/3D)]
                                                        │
                                                        ▼
                                            [映像出力 (OBS/直接配信)]
```

### 3. 感情エンジン

**入力:** テキスト（台本 or Gateway応答）
**出力:** 感情タグ + TTS指示 + アバター指示

```json
{
  "text": "マジっすか！やばいっすね！",
  "emotion": {
    "primary": "excited",
    "intensity": 0.8,
    "secondary": "happy"
  },
  "tts_instruction": "興奮した声で、テンション高めに",
  "avatar_instruction": {
    "expression": "surprised_happy",
    "gesture": "jump",
    "head_tilt": 15
  }
}
```

**感情分析方法:**
1. ルールベース（キーワード、絵文字、句読点パターン）
2. LLM分析（OpenClaw経由で感情タグ付け）
3. 台本に直接感情タグを埋め込み（収録モード）

### 4. TTS統合

**対応TTS:**
- Qwen3-TTS（推奨、ローカル、高品質）
- MeloTTS（軽量、高速）
- Edge TTS（クラウド、無料）
- ElevenLabs（クラウド、高品質）
- VOICEVOX（ローカル、日本語特化）
- カスタムAPI（OpenAI互換）

**TTS設定:**
```yaml
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
```

### 5. アバターエンジン

**対応フォーマット:**
- **2D:** Live2D (.moc3), PNG立ち絵（パーツ切り替え）
- **3D:** VRM, VRoid

**機能:**
- リップシンク（音声波形 or フォネーム連動）
- 表情切り替え（感情連動）
- ポーズ/ジェスチャー
- 目パチ、呼吸などアイドルモーション
- 物理演算（髪揺れ等）

### 6. 配信/出力

**出力先:**
- OBS（NDI or 仮想カメラ）
- 直接配信（YouTube Live API, Twitch API）
- 動画ファイル出力（収録モード）

**配信機能（ライブモード）:**
- コメント取得（YouTube/Twitch API）
- スパチャ/投げ銭反応
- コメントフィルタリング
- コメント読み上げキュー管理

## 追加機能（Phase 2以降）

### 7. シーン管理
- 背景切り替え
- カメラアングル（アップ/引き）
- オーバーレイ（テロップ、エフェクト）

### 8. BGM/SE管理
- BGMプレイリスト
- 効果音トリガー（リアクション連動）
- 音量オートダッキング

### 9. 字幕生成
- リアルタイム字幕表示
- SRT/VTT出力（収録モード）
- 翻訳字幕（多言語対応）

### 10. アーカイブ/クリップ
- 自動ハイライト検出
- クリップ切り出し
- サムネイル自動生成

## 技術スタック

### バックエンド
- **言語:** Python 3.11+
- **フレームワーク:** FastAPI（WebSocket + REST）
- **非同期:** asyncio

### フロントエンド
- **フレームワーク:** Electron + React/Vue
- **レンダリング:** PixiJS（2D）, Three.js（3D）
- **Live2D:** pixi-live2d-display

### 連携
- **OpenClaw:** HTTP API（chatCompletions）
- **YouTube:** YouTube Data API v3 + Live Streaming API
- **Twitch:** IRC + EventSub
- **OBS:** obs-websocket

## ディレクトリ構造

```
lobby/
├── backend/
│   ├── api/              # FastAPI routes
│   ├── core/
│   │   ├── emotion.py    # 感情エンジン
│   │   ├── tts.py        # TTS統合
│   │   ├── avatar.py     # アバター制御
│   │   └── openclaw.py   # OpenClaw連携
│   ├── modes/
│   │   ├── recording.py  # 収録モード
│   │   ├── live.py       # ライブモード
│   │   └── dialogue.py   # 対話モード
│   └── integrations/
│       ├── youtube.py
│       ├── twitch.py
│       └── obs.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── renderer/     # 2D/3D描画
│   │   └── views/
│   └── public/
├── models/               # アバターモデル置き場
├── scripts/              # 台本置き場
├── config/
│   └── lobby.yaml        # 設定ファイル
└── docs/
```

## 台本フォーマット

### シンプル版（.txt）
```
おはロビィ！僕、倉土ロビィっす！
[excited] マジでびっくりしたっす！
[sad] ちょっと寂しかったっすね...
```

### 詳細版（.json）
```json
{
  "title": "ロビィ自己紹介",
  "scenes": [
    {
      "id": "intro",
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
          "gesture": "point_self"
        }
      ]
    }
  ]
}
```

## 開発フェーズ

### Phase 1: MVP（1週間）
- [x] プロジェクト初期設定
- [x] 収録モード基本実装
- [x] Qwen3-TTS統合
- [x] 基本リップシンク（PNG立ち絵）
- [x] 動画出力

### Phase 2: Live2D対応（1週間）
- [x] Live2Dパラメータ生成（Live2DLipsyncAnalyzer）
- [x] WebSocket API（リアルタイムストリーム）
- [x] 表情プリセット（6種類）
- [x] Live2Dレンダリング（フロントエンド）
- [x] 感情エンジン統合（EmotionDrivenLive2D）
- [x] 物理演算連携（目パチ、呼吸、重力・風設定）

### Phase 3: ライブ配信（1週間）
- [x] OpenClaw Gateway連携（OpenClawClient, LiveMode）
- [x] ライブモードAPI（REST + WebSocket）
- [ ] YouTubeコメント取得
- [ ] リアルタイム応答テスト
- [ ] OBS出力

### Phase 4: 拡張機能
- [ ] 3D（VRM）対応
- [ ] Twitch対応
- [ ] BGM/SE管理
- [ ] シーン管理

## 差別化ポイント

| 機能 | Open-LLM-VTuber | OBS + VTube Studio | **Lobby** |
|------|-----------------|-------------------|-----------|
| OpenClaw連携 | 改造必要 | 不可 | **ネイティブ** |
| 台本収録 | 不可 | 不可 | **対応** |
| 感情エンジン | なし | なし | **搭載** |
| 配信統合 | なし | 別ソフト | **統合** |
| オープンソース | ✅ | ❌ | **✅** |

---

## フロントエンド構成

### 技術スタック
- **フレームワーク:** React 18 + TypeScript
- **ビルド:** Vite 5
- **パッケージマネージャ:** pnpm（npm互換性問題あり）
- **2D描画:** PixiJS 7
- **Live2D:** pixi-live2d-display（Cubism4対応）
- **デスクトップ:** Electron（予定）

### コンポーネント構成
```
frontend/src/
├── main.tsx              # エントリーポイント
├── App.tsx               # メインレイアウト
├── index.css             # グローバルスタイル
├── components/
│   ├── Live2DViewer.tsx  # PixiJS + Live2D描画
│   └── ControlPanel.tsx  # 表情・パラメータ操作
└── hooks/
    └── useLive2DWebSocket.ts  # WebSocket接続
```

### 開発コマンド
```bash
cd frontend
pnpm install        # 依存関係インストール
pnpm run dev        # 開発サーバー起動 (localhost:5173)
pnpm run build      # プロダクションビルド
```

---

*最終更新: 2026-02-11 21:35*
