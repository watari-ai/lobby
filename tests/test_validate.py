"""Tests for lobby validate command."""

import tempfile

from typer.testing import CliRunner

from backend.cli import app

runner = CliRunner()


def test_validate_text_script():
    """validate parses and reports on a text script."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("おはロビィ！\n[excited] マジっすか！\n[sad] 寂しいっす...\n")
        f.flush()
        result = runner.invoke(app, ["validate", f.name])
    assert result.exit_code == 0
    assert "行数:" in result.output
    assert "3" in result.output
    assert "感情分布" in result.output
    assert "バリデーション完了" in result.output


def test_validate_json_script():
    """validate parses JSON scripts."""
    import json
    script = {
        "title": "テスト台本",
        "scenes": [{
            "id": "s1",
            "lines": [
                {"text": "こんにちは", "emotion": "happy"},
                {"text": "さようなら", "emotion": "sad"},
            ]
        }]
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(script, f, ensure_ascii=False)
        f.flush()
        result = runner.invoke(app, ["validate", f.name])
    assert result.exit_code == 0
    assert "テスト台本" in result.output
    assert "2" in result.output


def test_validate_verbose():
    """validate --verbose shows all lines."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("テスト行1\nテスト行2\n")
        f.flush()
        result = runner.invoke(app, ["validate", "--verbose", f.name])
    assert result.exit_code == 0
    assert "全行:" in result.output


def test_validate_missing_file():
    """validate fails on missing file."""
    result = runner.invoke(app, ["validate", "/tmp/no_such_script.txt"])
    assert result.exit_code == 1


def test_validate_long_line_warning():
    """validate warns about long lines."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("あ" * 250 + "\n")
        f.flush()
        result = runner.invoke(app, ["validate", f.name])
    assert result.exit_code == 0
    assert "長すぎ" in result.output


def test_validate_emotion_hint_warning():
    """validate warns when neutral line has exclamation marks."""
    # Use a mild sentence with single ？ — emotion analyzer keeps it neutral
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("そうなんですか？\n")
        f.flush()
        result = runner.invoke(app, ["validate", f.name])
    assert result.exit_code == 0
    assert "タグ付け推奨" in result.output
