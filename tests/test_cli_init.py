"""Tests for lobby init command."""


from typer.testing import CliRunner

from backend.cli import app

runner = CliRunner()


def test_init_creates_directories(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    for d in ["scripts", "models", "output", "config"]:
        assert (tmp_path / d).is_dir()


def test_init_creates_config(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    config = tmp_path / "config" / "lobby.yaml"
    assert config.exists()
    content = config.read_text()
    assert "tts:" in content
    assert "avatar:" in content


def test_init_creates_sample_script(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    sample = tmp_path / "scripts" / "sample.txt"
    assert sample.exists()
    assert "ロビィ" in sample.read_text()


def test_init_creates_gitignore(tmp_path):
    runner.invoke(app, ["init", str(tmp_path)])
    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert "output/" in gitignore.read_text()


def test_init_does_not_overwrite_existing(tmp_path):
    config = tmp_path / "config" / "lobby.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("custom: true")

    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert config.read_text() == "custom: true"
    assert "already exists" in result.stdout


def test_init_with_custom_name(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path), "--name", "MyVTuber"])
    assert result.exit_code == 0
    config = (tmp_path / "config" / "lobby.yaml").read_text()
    assert "MyVTuber" in config


def test_init_current_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / "config" / "lobby.yaml").exists()
