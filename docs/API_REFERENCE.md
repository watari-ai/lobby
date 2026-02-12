# Lobby API Reference

バックエンドAPIの完全なリファレンスドキュメント。

## 概要

- **Base URL:** `http://localhost:8100`
- **OpenAPI Docs:** `http://localhost:8100/docs`
- **ReDoc:** `http://localhost:8100/redoc`

## 目次

1. [ヘルスチェック](#ヘルスチェック)
2. [Live2D WebSocket API](#live2d-websocket-api)
3. [ライブモードAPI](#ライブモードapi)
4. [OBS連携API](#obs連携api)
5. [オーディオAPI](#オーディオapi)
6. [シーン管理API](#シーン管理api)
7. [VRM (3D) API](#vrm-3d-api)
8. [字幕API](#字幕api)
9. [ハイライト検出API](#ハイライト検出api)
10. [クリップ抽出API](#クリップ抽出api)
11. [サムネイル生成API](#サムネイル生成api)

---

## ヘルスチェック

### GET /

アプリケーション情報を取得。

**レスポンス:**
```json
{
  "name": "Lobby",
  "version": "0.2.0",
  "status": "running"
}
```

### GET /health

ヘルスチェック。

**レスポンス:**
```json
{
  "status": "healthy"
}
```

---

## Live2D WebSocket API

### WebSocket /ws/live2d

Live2Dパラメータのリアルタイムストリーミング。

**接続:**
```javascript
const ws = new WebSocket('ws://localhost:8100/ws/live2d');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: "parameters" | "frame" | "expression" | "motion"
};
```

**受信メッセージ:**

| type | 説明 |
|------|------|
| `parameters` | Live2Dパラメータ（目、口、体の位置など） |
| `frame` | フレームデータ（パラメータ + 表情 + モーション） |
| `expression` | 表情変更通知 |
| `motion` | モーション再生通知 |

**送信コマンド:**

```json
// 表情セット
{"action": "set_expression", "expression": "happy"}

// リップシンク開始
{"action": "start_lipsync", "audio_path": "/path/to/audio.wav"}

// モーション再生
{"action": "play_motion", "motion": "wave"}
```

**パラメータ例:**
```json
{
  "type": "parameters",
  "data": {
    "eyeOpenL": 1.0,
    "eyeOpenR": 1.0,
    "mouthOpen": 0.0,
    "mouthForm": 0.5,
    "bodyAngleX": 0.0,
    "bodyAngleY": 0.0,
    "bodyAngleZ": 0.0,
    "breathValue": 0.5
  }
}
```

---

## ライブモードAPI

### GET /api/live/status

ライブモードのステータス取得。

**レスポンス:**
```json
{
  "running": false,
  "queue_size": 0,
  "gateway_url": null
}
```

### POST /api/live/start

ライブモード開始。

**リクエスト:**
```json
{
  "gateway_url": "http://localhost:18789",
  "tts_url": "http://localhost:8001",
  "tts_voice": "lobby",
  "system_prompt": "あなたはロビィです..."
}
```

**レスポンス:**
```json
{
  "status": "started",
  "gateway_url": "http://localhost:18789"
}
```

### POST /api/live/stop

ライブモード停止。

### POST /api/live/input

入力追加（コメント等）。

**リクエスト:**
```json
{
  "text": "こんにちは！",
  "source": "youtube",
  "author": "視聴者A",
  "author_id": "UC...",
  "metadata": {}
}
```

### POST /api/live/chat

単発チャット（テスト用）。

**リクエスト:**
```json
{
  "text": "調子はどう？",
  "author": "User"
}
```

### WebSocket /api/live/ws

ライブモード出力のリアルタイムストリーム。

---

## OBS連携API

### GET /obs/status

OBS接続ステータス。

**レスポンス:**
```json
{
  "connected": false,
  "host": null,
  "port": null
}
```

### POST /obs/connect

OBSに接続。

**リクエスト:**
```json
{
  "host": "localhost",
  "port": 4455,
  "password": "your-password"
}
```

### POST /obs/disconnect

OBS切断。

### GET /obs/scenes

シーン一覧取得。

**レスポンス:**
```json
{
  "scenes": [
    {"scene_name": "メイン", "scene_index": 0},
    {"scene_name": "休憩", "scene_index": 1}
  ],
  "current_scene": "メイン"
}
```

### POST /obs/scene

シーン切り替え。

**リクエスト:**
```json
{
  "scene_name": "休憩"
}
```

### GET /obs/scene/{scene_name}/items

シーンアイテム一覧。

### POST /obs/scene/item/enabled

アイテム表示/非表示。

**リクエスト:**
```json
{
  "scene_name": "メイン",
  "item_id": 1,
  "enabled": true
}
```

### POST /obs/virtual-camera/start

仮想カメラ開始。

### POST /obs/virtual-camera/stop

仮想カメラ停止。

### POST /obs/record/start

録画開始。

### POST /obs/record/stop

録画停止。

---

## オーディオAPI

### GET /audio/status

オーディオ状態。

### GET /audio/playlists

プレイリスト一覧。

### POST /audio/playlist

プレイリスト作成。

**リクエスト:**
```json
{
  "name": "配信用BGM",
  "tracks": [
    {"id": "bgm1", "path": "/path/to/music.mp3", "name": "チル", "volume": 0.8}
  ]
}
```

### POST /audio/playlist/load

ディレクトリからプレイリスト読み込み。

**リクエスト:**
```json
{
  "name": "新プレイリスト",
  "directory": "/path/to/music/folder"
}
```

### POST /audio/bgm/play

BGM再生開始。

### POST /audio/bgm/pause

BGM一時停止。

### POST /audio/bgm/stop

BGM停止。

### POST /audio/bgm/next

次の曲。

### POST /audio/bgm/prev

前の曲。

### POST /audio/volume

音量設定。

**リクエスト:**
```json
{
  "channel": "bgm",
  "volume": 0.5
}
```

### POST /audio/mute

ミュート設定。

**リクエスト:**
```json
{
  "channel": "bgm",
  "muted": true
}
```

### GET /audio/se

効果音一覧。

### POST /audio/se

効果音追加。

**リクエスト:**
```json
{
  "id": "applause",
  "path": "/path/to/applause.mp3",
  "name": "拍手",
  "trigger": "happy",
  "volume": 1.0,
  "cooldown": 0.5
}
```

### POST /audio/se/play

効果音再生。

**リクエスト:**
```json
{
  "se_id": "applause"
}
```

または

```json
{
  "trigger": "happy"
}
```

### POST /audio/ducking

ダッキング設定。

**リクエスト:**
```json
{
  "enabled": true,
  "target_volume": 0.3,
  "fade_duration": 0.5
}
```

---

## シーン管理API

### GET /api/scene/list

シーン一覧。

### GET /api/scene/current

現在のシーン。

### POST /api/scene/create

シーン作成。

**リクエスト:**
```json
{
  "name": "オープニング",
  "background": {
    "type": "image",
    "path": "/path/to/bg.png"
  },
  "camera": {
    "angle": "close_up",
    "zoom": 1.2
  },
  "overlays": []
}
```

### POST /api/scene/switch

シーン切り替え。

**リクエスト:**
```json
{
  "name": "オープニング",
  "transition": "fade"
}
```

### POST /api/scene/camera

カメラ設定変更。

**リクエスト:**
```json
{
  "angle": "medium",
  "zoom": 1.0,
  "offset_x": 0.0,
  "offset_y": 0.0
}
```

### POST /api/scene/overlay

オーバーレイ追加。

**リクエスト:**
```json
{
  "id": "title",
  "type": "text",
  "content": "ロビィの配信！",
  "position": [0.5, 0.1],
  "size": [0.8, 0.1],
  "style": {"fontSize": 48, "color": "#ffffff"}
}
```

### DELETE /api/scene/overlay/{id}

オーバーレイ削除。

### POST /api/scene/caption

テロップ表示。

**リクエスト:**
```json
{
  "text": "チャンネル登録よろしく！",
  "duration_ms": 5000
}
```

---

## VRM (3D) API

### GET /vrm/info

VRMモデル情報。

**レスポンス:**
```json
{
  "loaded": true,
  "path": "/path/to/model.vrm",
  "vrmVersion": "1.0",
  "title": "ロビィ",
  "author": "作者名",
  "expressions": ["happy", "sad", "angry", "surprised", "neutral"]
}
```

### POST /vrm/load

VRMモデル読み込み。

**リクエスト:**
```json
{
  "path": "/path/to/model.vrm"
}
```

### GET /vrm/state

現在の状態。

### POST /vrm/emotion

感情セット。

**リクエスト:**
```json
{
  "emotion": "happy",
  "intensity": 0.8
}
```

### POST /vrm/viseme

口形状セット（リップシンク用）。

**リクエスト:**
```json
{
  "phoneme": "a",
  "intensity": 1.0
}
```

### POST /vrm/look-at

視線方向セット。

**リクエスト:**
```json
{
  "x": 0.2,
  "y": -0.1
}
```

### GET /vrm/presets

利用可能なプリセット一覧。

---

## 字幕API

### WebSocket /ws/subtitle

リアルタイム字幕WebSocket。

**送信コマンド:**
```json
{"action": "show", "text": "こんにちは！", "speaker": "ロビィ", "emotion": "happy"}
{"action": "clear"}
{"action": "get_current"}
{"action": "get_history", "limit": 10}
{"action": "export", "format": "srt"}
```

**受信メッセージ:**
```json
{
  "type": "subtitle",
  "action": "show",
  "data": {
    "id": "sub_001",
    "text": "こんにちは！",
    "speaker": "ロビィ",
    "emotion": "happy",
    "start_ms": 0,
    "end_ms": 3000
  }
}
```

### POST /api/subtitle/show

字幕表示。

**リクエスト:**
```json
{
  "text": "今日も配信がんばるっす！",
  "speaker": "ロビィ",
  "emotion": "excited",
  "duration_ms": 4000
}
```

### POST /api/subtitle/clear

字幕クリア。

### GET /api/subtitle/current

現在の字幕。

### GET /api/subtitle/history

字幕履歴。

### POST /api/subtitle/export

字幕エクスポート（SRT/VTT）。

**リクエスト:**
```json
{
  "format": "srt"
}
```

### POST /api/subtitle/translate

字幕翻訳。

**リクエスト:**
```json
{
  "text": "こんにちは！",
  "target_language": "en"
}
```

---

## ハイライト検出API

### POST /api/highlight/start

ハイライト検出セッション開始。

**リクエスト:**
```json
{
  "config": {
    "audio_threshold": 0.7,
    "emotion_threshold": 0.7,
    "chat_burst_threshold": 5,
    "highlight_keywords": ["やばい", "すごい", "草"]
  }
}
```

### POST /api/highlight/stop

セッション停止＆ハイライト取得。

### POST /api/highlight/marker

手動マーカー追加。

**リクエスト:**
```json
{
  "label": "神プレイ",
  "timestamp_ms": 120000
}
```

### GET /api/highlight/list

ハイライト一覧。

### GET /api/highlight/top

上位ハイライト。

**クエリパラメータ:**
- `n`: 件数（デフォルト: 5）

### GET /api/highlight/chapters

YouTubeチャプター生成。

**クエリパラメータ:**
- `video_duration_ms`: 動画長（ミリ秒）

### POST /api/highlight/export

ハイライトエクスポート。

**リクエスト:**
```json
{
  "output_path": "/path/to/highlights.json"
}
```

---

## クリップ抽出API

### GET /api/clip/status

クリップ抽出ステータス。

### POST /api/clip/extract

クリップ抽出。

**リクエスト:**
```json
{
  "video_path": "/path/to/video.mp4",
  "start_ms": 60000,
  "end_ms": 70000,
  "output_path": "/path/to/clip.mp4",
  "format": "mp4"
}
```

### POST /api/clip/from-highlight

ハイライトからクリップ抽出。

**リクエスト:**
```json
{
  "video_path": "/path/to/video.mp4",
  "highlight_timestamp_ms": 120000,
  "highlight_duration_ms": 5000,
  "highlight_type": "audio_spike",
  "highlight_label": "絶叫"
}
```

### POST /api/clip/auto

自動ハイライト検出＆クリップ抽出。

**リクエスト:**
```json
{
  "video_path": "/path/to/video.mp4",
  "output_dir": "/path/to/clips",
  "max_clips": 5,
  "create_reel": true
}
```

### POST /api/clip/reel

ハイライトリール作成。

**リクエスト:**
```json
{
  "video_path": "/path/to/video.mp4",
  "highlight_timestamps_ms": [30000, 60000, 120000],
  "output_path": "/path/to/reel.mp4",
  "add_transitions": true
}
```

---

## サムネイル生成API

### GET /api/thumbnail/status

サムネイル生成ステータス。

### POST /api/thumbnail/generate

サムネイル自動生成。

**リクエスト:**
```json
{
  "video_path": "/path/to/video.mp4",
  "output_dir": "/path/to/thumbnails",
  "sizes": [
    {"name": "youtube", "width": 1280, "height": 720},
    {"name": "twitter", "width": 1200, "height": 675}
  ],
  "text_overlay": "【神回】ロビィ絶叫配信"
}
```

### POST /api/thumbnail/at-timestamp

特定時刻でサムネイル生成。

**リクエスト:**
```json
{
  "video_path": "/path/to/video.mp4",
  "timestamp_ms": 120000,
  "output_dir": "/path/to/thumbnails",
  "text_overlay": "ここがクライマックス！"
}
```

### POST /api/thumbnail/from-highlight

ハイライトからサムネイル生成。

**リクエスト:**
```json
{
  "video_path": "/path/to/video.mp4",
  "highlight": {
    "timestamp_ms": 120000,
    "duration_ms": 5000,
    "type": "audio_spike",
    "score": 0.95,
    "label": "絶叫"
  }
}
```

---

## エラーレスポンス

エラー時は以下の形式で返却:

```json
{
  "detail": "Error message here"
}
```

HTTPステータスコード:
- `400` - Bad Request（リクエスト不正）
- `404` - Not Found（リソース未存在）
- `422` - Validation Error（バリデーションエラー）
- `500` - Internal Server Error（サーバーエラー）

---

## 認証

現在のバージョンでは認証は実装されていません。ローカル環境での使用を想定しています。

---

*最終更新: 2026-02-13*
