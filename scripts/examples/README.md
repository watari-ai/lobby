# サンプル台本

Lobby収録モードで使用できるサンプル台本集です。

## ファイル一覧

### hello_lobby.txt
シンプルなテキスト形式の台本。感情タグ `[happy]`, `[excited]` 等で表情を制御。

**使い方:**
```bash
lobby record --script scripts/examples/hello_lobby.txt --output output/hello.mp4
```

### self_introduction.json
詳細なJSON形式の台本。シーン分割、ジェスチャー、待機時間など細かく制御可能。

**使い方:**
```bash
lobby record --script scripts/examples/self_introduction.json --output output/intro.mp4
```

## 台本フォーマット

### テキスト形式 (.txt)
```
普通のテキスト
[emotion] 感情タグ付きテキスト
# コメント行（読み飛ばされる）
```

**対応感情:**
- `[happy]` - 嬉しい
- `[sad]` - 悲しい
- `[excited]` - 興奮
- `[angry]` - 怒り
- `[surprised]` - 驚き
- `[neutral]` - 通常

### JSON形式 (.json)
シーンとセリフを構造化して記述。詳細は[DESIGN.md](../../docs/DESIGN.md)参照。

## カスタム台本の作成

1. このフォルダのサンプルをコピー
2. テキストを編集
3. `lobby record` コマンドで収録

詳しくは [チュートリアル](../../docs/TUTORIAL.md) を参照してください。
