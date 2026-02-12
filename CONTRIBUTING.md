# Contributing to Lobby

まずは、Lobbyへの貢献に興味を持っていただきありがとうございます！🦞

## 開発環境のセットアップ

### 必要なもの

- Python 3.11以上
- Node.js 20以上
- pnpm

### バックエンドセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/watari-ai/lobby.git
cd lobby

# Python仮想環境を作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 開発用依存関係をインストール
pip install -e ".[dev]"

# テスト実行
pytest
```

### フロントエンドセットアップ

```bash
cd frontend

# 依存関係をインストール
pnpm install

# 開発サーバー起動
pnpm run dev

# Electron開発モード
pnpm run electron:dev
```

## 開発ワークフロー

### ブランチ戦略

- `main` - 安定版リリースブランチ
- `develop` - 開発ブランチ
- `feature/*` - 新機能
- `fix/*` - バグ修正
- `docs/*` - ドキュメント更新

### コミットメッセージ

[Conventional Commits](https://www.conventionalcommits.org/)に従ってください：

```
feat: 新機能を追加
fix: バグを修正
docs: ドキュメントを更新
style: コードスタイルを変更（機能変更なし）
refactor: リファクタリング
test: テストを追加/修正
chore: ビルド/ツール設定の変更
```

絵文字プレフィックスも推奨：

```
✨ feat: 新機能を追加
🐛 fix: バグを修正
📝 docs: ドキュメントを更新
🎨 style: コードスタイルを変更
♻️ refactor: リファクタリング
✅ test: テストを追加
🔧 chore: 設定の変更
```

### プルリクエスト

1. `develop`からブランチを作成
2. 変更を実装
3. テストを追加/更新
4. すべてのテストが通ることを確認
5. PRを作成

#### PRチェックリスト

- [ ] テストを追加/更新した
- [ ] `pytest`がすべてパスする
- [ ] フロントエンドの場合、`pnpm run build`が成功する
- [ ] ドキュメントを更新した（必要な場合）
- [ ] CHANGELOG.mdを更新した

## コードスタイル

### Python

- フォーマッター: [Black](https://black.readthedocs.io/)
- リンター: [Ruff](https://docs.astral.sh/ruff/)
- 型ヒント: 必須

```bash
# フォーマット
black backend/

# リント
ruff check backend/
```

### TypeScript/React

- フォーマッター: Prettier
- リンター: ESLint
- コンポーネント: 関数コンポーネント + Hooks

```bash
cd frontend

# リント
pnpm run lint

# フォーマット
pnpm run format
```

## テスト

### バックエンドテスト

```bash
# すべてのテスト
pytest

# カバレッジ付き
pytest --cov=backend

# 特定のテスト
pytest tests/test_emotion.py
```

### フロントエンドテスト

```bash
cd frontend
pnpm run test
```

## ドキュメント

ドキュメントは`docs/`ディレクトリにあります：

- `DESIGN.md` - 設計書
- `API_REFERENCE.md` - API仕様
- `TUTORIAL.md` - チュートリアル
- `WEB_UI_DESIGN.md` - Web UI設計

新機能を追加したら、関連するドキュメントも更新してください。

## Issue

### バグ報告

バグを見つけたら、以下の情報を含めてIssueを作成してください：

- 環境（OS、Pythonバージョン、Node.jsバージョン）
- 再現手順
- 期待される動作
- 実際の動作
- エラーメッセージ（あれば）

### 機能リクエスト

新機能のアイデアがあれば、Issueで提案してください。以下を含めると助かります：

- 解決したい問題
- 提案する解決策
- 代替案（検討したものがあれば）

## 質問

質問は[GitHub Discussions](https://github.com/watari-ai/lobby/discussions)でお気軽にどうぞ。

## ライセンス

貢献されたコードはMITライセンスの下で公開されます。

---

ご協力ありがとうございます！🦞
