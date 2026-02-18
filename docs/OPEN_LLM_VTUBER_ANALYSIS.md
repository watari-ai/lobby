# Open-LLM-VTuber vs Lobby 技術比較レポート

**調査日**: 2026-02-16
**Open-LLM-VTuber**: `/Users/w/Open-LLM-VTuber/` (GitHub: Open-LLM-VTuber/Open-LLM-VTuber)
**Lobby**: `/Users/w/lobby/`

---

## 概要

3つの指摘事項（動き速度、リップシンク、感情連動）について、両プロジェクトのソースを分析した。

---

## 1. Live2Dモデルの動き速度

### 問題
Lobbyは動きがゆっくり、Open-LLM-VTuberはサクサク動く。

### 原因分析

| 項目 | Lobby | Open-LLM-VTuber |
|------|-------|------------------|
| 補間方式 | フレームごとに `smoothing × (delta/16.67)` で線形補間 | フロントエンドで音量配列を直接参照（補間なし） |
| smoothing値 | **0.25**（App.tsx）/ デフォルト0.3 | N/A（補間レイヤーなし） |
| パラメータ更新 | WebSocket → state更新 → React再レンダー → targetParams更新 → 補間ループで徐々に反映 | WebSocket → 音声+volumes配列を一括受信 → 音声再生と同期してvolumeから直接ParamMouthOpenYを設定 |
| ボトルネック | **React state更新を経由**するため、パラメータ反映が2段階遅延 | 音声データとvolume配列が事前計算済みで即座に適用 |

### 根本原因
**Lobbyのsmoothing=0.25が低すぎる。** `t = 0.25 × (delta/16.67)` は60fpsで1フレームあたり25%しか目標値に近づかない。実質的に4-5フレーム（67-83ms）遅延する。

加えて、パラメータ更新が `props.params → targetParams → animationLoop → currentParams → applyParams` と多段パイプラインを通るため、反応が鈍い。

### 改善案
1. **smoothing値を0.6-0.8に引き上げ**（即効性あり、最小変更）
2. **リップシンク用パラメータは補間をバイパス**して直接適用（ParamMouthOpenYのみ即時反映）
3. 長期的には、Open-LLM-VTuber方式の「事前計算されたvolume配列 + 音声再生同期」に移行

---

## 2. リップシンク

### Open-LLM-VTuberの実装

**バックエンド側** (`utils/stream_audio.py`):
- TTS生成後、音声を`pydub`で20msチャンクに分割
- 各チャンクのRMS（音量）を計算し、最大値で正規化（0.0〜1.0）
- `volumes`配列と`slice_length`（20ms）をフロントエンドにWebSocketで送信

```python
# prepare_audio_payload の核心部分
chunks = make_chunks(audio, chunk_length_ms=20)
volumes = [chunk.rms / max_volume for chunk in chunks]
payload = {"audio": base64_wav, "volumes": volumes, "slice_length": 20}
```

**フロントエンド側**（ビルド済みJS、ソース未入手）:
- 音声再生中に20ms間隔で`volumes`配列からインデックスを進める
- volume値をそのまま`ParamMouthOpenY`に設定
- **expression（表情インデックス）** はactions.expressionsとして送信され、model3.jsonのExpressions配列のインデックスで指定

**キーポイント**: リップシンクは「リアルタイム音声解析」ではなく、**バックエンド事前計算 + 同期再生**方式。

### Lobbyの実装

**バックエンド側** (`backend/core/live2d.py`):
- `Live2DLipsyncAnalyzer.analyze_audio()`でwavファイルをRMS解析
- フレームごとにパラメータを生成（30fps、まばたき・呼吸含む）
- `EmotionDrivenLive2D.generate_speaking_frames()`で感情分析+リップシンク統合済み

**フロントエンド側** (`hooks/useLive2DWebSocket.ts`):
- WebSocketから`parameters`/`frame`メッセージを受信
- React stateを更新し、Live2DViewer.tsxの補間ループで反映

**問題点**:
- バックエンドでLive2Dフレームを事前生成しているが、**フロントエンドへの送信・同期メカニズムが不明確**
- WebSocketで個別フレームを送信すると、ネットワーク遅延 × フレーム数のオーバーヘッド
- 補間レイヤーがリップシンクの応答性を殺している

### 改善案
1. **Open-LLM-VTuber方式を採用**: 音声base64 + volumes配列 + slice_length を一括送信
2. フロントエンドでAudio再生位置に合わせてvolumes配列からインデックスを計算
3. **ParamMouthOpenYだけは補間をスキップ**して直接反映（他パラメータは補間維持）

---

## 3. 感情エンジン連動

### Open-LLM-VTuberの実装

**感情→表情マッピング** (`live2d_model.py`):
- `model_dict.json`でモデルごとに`emotionMap`を定義
  ```json
  {"neutral": 0, "anger": 2, "fear": 1, "joy": 3, "sadness": 1, "surprise": 3}
  ```
- 数値はmodel3.jsonの**Expressionsインデックス**（表情ファイル参照）
- LLMの出力に`[joy]`, `[anger]`等のタグを埋め込み、`extract_emotion()`で抽出

**感情タグの注入** (`agent/transformers.py`):
- `actions_extractor`デコレータがLLM出力ストリームから感情タグを抽出
- `Actions(expressions=[3])`のように表情インデックスリストを生成
- 音声ペイロードの`actions`フィールドとしてフロントエンドに送信

**フロントエンド側**:
- `actions.expressions`を受け取り、Live2D SDKの`model.expression(index)`で表情切替
- **model3.jsonのExpressionsファイル**（.exp3.json）がパラメータセットを定義

### Lobbyの実装

**感情分析** (`backend/core/emotion.py`):
- `EmotionAnalyzer`: タグベース (`[happy]`) + キーワードベースの分析
- 6感情: happy, sad, excited, angry, surprised, neutral

**感情→Live2D** (`backend/core/live2d.py`):
- `Live2DConfig.expression_presets`: 各感情に対する**パラメータオフセット**を定義
  - 例: HAPPY → `{param_mouth_form: 0.5, param_eye_l_open: 0.9, ...}`
- `EmotionDrivenLive2D`クラスが統合処理を担当

**重要な違い**:

| 項目 | Lobby | Open-LLM-VTuber |
|------|-------|------------------|
| 表情データ | コード内のパラメータオフセット（6種） | model3.jsonのExpressions (.exp3.json) |
| 切替方式 | パラメータ加算で徐々に変化 | SDK標準のexpression API（即時切替） |
| 表情の豊かさ | パラメータ3-4個の微調整 | モデル作者が定義した完全な表情セット |
| LLM統合 | ルールベース感情分析（後付け） | LLMプロンプトに感情タグを要求 |

### 問題点
Lobbyの「パラメータオフセット加算」方式は**表情変化が微妙すぎて分からない**。Open-LLM-VTuberは**Live2D SDKの表情機能をフル活用**しており、モデルに含まれる表情データ（.exp3.json）をそのまま使うため、見た目の変化が大きい。

### 改善案
1. **Live2D SDKのExpression APIを使用**: `model.expression(index)`でモデル内蔵表情を切替
2. モデルのExpressions一覧を読み取り、感情→表情インデックスのマッピングを設定可能に
3. **LLMプロンプトに感情タグを埋め込む指示を追加**（Open-LLM-VTuber方式）
4. 現在のパラメータオフセット方式は、Expression非対応モデルのフォールバックとして残す

---

## 実装優先度

| # | 項目 | 効果 | 工数 | 推奨 |
|---|------|------|------|------|
| 1 | **smoothing値を0.6-0.8に変更** | 中 | 1行変更 | ★★★ 即実行 |
| 2 | **音声+volumes一括送信方式** | 高 | 2-3日 | ★★★ リップシンク根本解決 |
| 3 | **Expression API活用** | 高 | 1-2日 | ★★☆ 表情の豊かさ向上 |
| 4 | **ParamMouthOpenY補間バイパス** | 中 | 数時間 | ★★☆ リップシンク即応性 |
| 5 | **LLMプロンプトに感情タグ指示** | 中 | 数時間 | ★★☆ 感情検出精度向上 |
| 6 | **感情→表情マッピング設定UI** | 低 | 1日 | ★☆☆ モデル汎用対応 |

---

## 技術的に移植すべき要素まとめ

### 必須
1. **volumes配列方式のリップシンク**: バックエンドでRMS事前計算 → 音声と一括送信 → フロントエンドで再生同期
2. **Live2D SDK Expression APIの活用**: パラメータ手動設定ではなく、モデル内蔵の表情ファイルを使う

### 推奨
3. **emotion map設定**: モデルごとの感情→表情インデックス対応表（model_dict.json相当）
4. **LLMプロンプトへの感情タグ埋め込み指示**: LLMに`[joy]`等のタグを出力させる

### 参考
5. Open-LLM-VTuberのmodel_dict.jsonの構造（kScale, kXOffset等のモデル配置パラメータ）
6. tapMotionsによるインタラクション（HitArea対応）
