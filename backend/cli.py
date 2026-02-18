"""Lobby CLI - コマンドラインインターフェース"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .core.avatar import AvatarParts, LipsyncConfig
from .core.config import load_config, build_pipeline_config, build_tts_config
from .core.pipeline import BGMConfig, PipelineConfig, RecordingPipeline
from .core.tts import TTSClient, TTSConfig
from .core.video import VideoConfig
from .modes.recording import RecordingMode, Script

app = typer.Typer(
    name="lobby",
    help="Lobby - AI VTuber配信・収録ソフト",
    add_completion=False,
)
console = Console()


@app.command()
def record(
    script_path: Path = typer.Argument(..., help="台本ファイルパス (.txt, .json)"),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="設定ファイルパス（lobby.yaml）",
    ),
    output_dir: Path = typer.Option(
        Path("./output"),
        "--output", "-o",
        help="出力ディレクトリ",
    ),
    tts_url: Optional[str] = typer.Option(
        None,
        "--tts-url",
        help="TTS APIのベースURL（MioTTS: 8001, Qwen3: 8880/v1）",
    ),
    voice: Optional[str] = typer.Option(
        None,
        "--voice", "-v",
        help="使用する音声（MioTTSプリセット: lobby, jp_female等）",
    ),
):
    """台本から音声を収録"""

    if not script_path.exists():
        console.print(f"[red]Error: Script not found: {script_path}[/red]")
        raise typer.Exit(1)

    async def _record():
        # 台本を読み込み
        console.print(f"[cyan]Loading script: {script_path}[/cyan]")
        script = Script.from_file(script_path)
        console.print(f"[green]Loaded: {script.title} ({len(script.lines)} lines)[/green]")

        # TTS設定: config > CLI args > defaults
        if config_path:
            data = load_config(config_path)
            tts_config = build_tts_config(data)
        else:
            tts_config = TTSConfig()

        # CLI引数でオーバーライド
        if tts_url:
            tts_config.base_url = tts_url
        if voice:
            tts_config.voice = voice

        # 収録
        async with RecordingMode(tts_config=tts_config, output_dir=output_dir) as recorder:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Recording...", total=len(script.lines))

                async for result in recorder.record_script(script):
                    progress.update(task, advance=1)
                    console.print(f"  ✓ {result.audio_path.name}")

        console.print("[green]✅ Recording complete![/green]")
        console.print(f"   Output: {output_dir / script.title.replace(' ', '_')}")

    asyncio.run(_record())


@app.command()
def record_video(
    script_path: Path = typer.Argument(..., help="台本ファイルパス (.txt, .json)"),
    avatar_base: Optional[Path] = typer.Argument(None, help="アバターベース画像パス（--config使用時は省略可）"),
    mouth_closed: Optional[Path] = typer.Argument(None, help="口閉じ画像パス（--config使用時は省略可）"),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="設定ファイルパス（lobby.yaml）。指定時はアバター・TTS等を設定から読み込み",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="出力ディレクトリ（デフォルト: ./output）",
    ),
    mouth_open: Optional[Path] = typer.Option(
        None,
        "--mouth-open",
        help="口開き画像パス（省略時は口閉じを使用）",
    ),
    background: Optional[Path] = typer.Option(
        None,
        "--background", "-bg",
        help="背景画像パス",
    ),
    tts_url: Optional[str] = typer.Option(
        None,
        "--tts-url",
        help="TTS APIのベースURL（MioTTS: 8001, Qwen3: 8880/v1）",
    ),
    voice: Optional[str] = typer.Option(
        None,
        "--voice", "-v",
        help="使用する音声（MioTTSプリセット: lobby等）",
    ),
    fps: Optional[int] = typer.Option(
        None,
        "--fps",
        help="フレームレート",
    ),
    burn_subtitles: Optional[bool] = typer.Option(
        None,
        "--burn-subtitles/--no-burn-subtitles",
        help="字幕を動画に焼き込む",
    ),
    bgm: Optional[Path] = typer.Option(
        None,
        "--bgm",
        help="BGMファイルパス（自動ダッキング付き）",
    ),
    bgm_volume: Optional[float] = typer.Option(
        None,
        "--bgm-volume",
        help="BGM音量 (0.0-1.0、デフォルト: 0.15)",
    ),
):
    """台本から動画を生成（フルパイプライン）

    使い方:
      # 設定ファイルから（推奨）
      lobby record-video script.txt --config config/lobby.yaml

      # 引数で直接指定
      lobby record-video script.txt avatar_base.png mouth_closed.png
    """

    if not script_path.exists():
        console.print(f"[red]Error: Script not found: {script_path}[/red]")
        raise typer.Exit(1)

    async def _record_video():
        # 台本を読み込み
        console.print(f"[cyan]Loading script: {script_path}[/cyan]")
        script = Script.from_file(script_path)
        console.print(f"[green]Loaded: {script.title} ({len(script.lines)} lines)[/green]")

        # 設定ファイルベース or CLI引数ベース
        if config_path:
            console.print(f"[cyan]Loading config: {config_path}[/cyan]")
            data = load_config(config_path)

            # CLI引数でオーバーライド
            if tts_url:
                data.setdefault("tts", {})["base_url"] = tts_url
            if voice:
                data.setdefault("tts", {})["voice"] = voice
            if fps:
                data.setdefault("lipsync", {})["fps"] = fps
                data.setdefault("video", {})["fps"] = fps
            if output_dir:
                data["output_dir"] = str(output_dir)
            if burn_subtitles is not None:
                data.setdefault("subtitle", {})["burn_in"] = burn_subtitles
            if bgm:
                data.setdefault("bgm", {})["path"] = str(bgm)
                data["bgm"]["enabled"] = True
            if bgm_volume is not None:
                data.setdefault("bgm", {})["volume"] = bgm_volume

            # アバターパーツ: CLI引数 > 設定ファイル
            if avatar_base:
                data.setdefault("avatar", {})["base"] = str(avatar_base)
            if mouth_closed:
                data.setdefault("avatar", {})["mouth_closed"] = str(mouth_closed)
            if mouth_open:
                data.setdefault("avatar", {})["mouth_open_s"] = str(mouth_open)
                data.setdefault("avatar", {})["mouth_open_m"] = str(mouth_open)
                data.setdefault("avatar", {})["mouth_open_l"] = str(mouth_open)

            try:
                pipeline_config = build_pipeline_config(data)
            except ValueError as e:
                console.print(f"[red]Config error: {e}[/red]")
                console.print("[yellow]Hint: Set avatar.base and avatar.mouth_closed in config[/yellow]")
                raise typer.Exit(1)

            if background:
                pipeline_config.background_image = background

        else:
            # 従来のCLI引数モード
            if not avatar_base or not mouth_closed:
                console.print("[red]Error: avatar_base and mouth_closed are required[/red]")
                console.print("[yellow]Hint: Use --config to load from lobby.yaml[/yellow]")
                raise typer.Exit(1)

            if not avatar_base.exists():
                console.print(f"[red]Error: Avatar base not found: {avatar_base}[/red]")
                raise typer.Exit(1)

            if not mouth_closed.exists():
                console.print(f"[red]Error: Mouth closed image not found: {mouth_closed}[/red]")
                raise typer.Exit(1)

            avatar_parts = AvatarParts(
                base=avatar_base,
                mouth_closed=mouth_closed,
                mouth_open_s=mouth_open,
                mouth_open_m=mouth_open,
                mouth_open_l=mouth_open,
            )

            bgm_config = BGMConfig(
                enabled=bgm is not None,
                path=bgm,
                volume=bgm_volume or 0.15,
            ) if bgm else BGMConfig()

            pipeline_config = PipelineConfig(
                tts=TTSConfig(
                    base_url=tts_url or "http://localhost:8001",
                    voice=voice or "lobby",
                ),
                lipsync=LipsyncConfig(fps=fps or 30),
                video=VideoConfig(fps=fps or 30),
                avatar_parts=avatar_parts,
                output_dir=output_dir or Path("./output"),
                background_image=background,
                bgm=bgm_config,
            )

        # パイプライン実行
        async with RecordingPipeline(pipeline_config) as pipeline:
            def progress_callback(current: int, total: int, status: str):
                console.print(f"  [{current}/{total}] {status}")

            output_path = await pipeline.process_script(script, progress_callback)
            console.print(f"[green]✅ Video created: {output_path}[/green]")

    asyncio.run(_record_video())


@app.command()
def tts_test(
    text: str = typer.Argument("おはロビィ！僕、倉土ロビィっす！", help="テストするテキスト"),
    output: Path = typer.Option(
        Path("./test_output.mp3"),
        "--output", "-o",
        help="出力ファイルパス",
    ),
    tts_url: str = typer.Option(
        "http://localhost:8001",
        "--tts-url",
        help="TTS APIのベースURL（MioTTS: 8001, Qwen3: 8880/v1）",
    ),
    voice: str = typer.Option(
        "lobby",
        "--voice", "-v",
        help="使用する音声（MioTTSプリセット: lobby等）",
    ),
    emotion: str = typer.Option(
        "neutral",
        "--emotion", "-e",
        help="感情（happy, sad, excited, angry, surprised, neutral）",
    ),
):
    """TTSのテスト"""

    async def _test():
        config = TTSConfig(base_url=tts_url, voice=voice)

        async with TTSClient(config) as client:
            # ヘルスチェック
            console.print(f"[cyan]Checking TTS server: {tts_url}[/cyan]")
            if not await client.check_health():
                console.print("[red]Error: TTS server not available[/red]")
                raise typer.Exit(1)
            console.print("[green]TTS server OK[/green]")

            # 音声生成
            console.print(f"[cyan]Generating: {text}[/cyan]")
            console.print(f"[cyan]Emotion: {emotion}, Voice: {voice}[/cyan]")

            await client.synthesize(
                text=text,
                emotion=emotion,
                output_path=output,
            )

            console.print(f"[green]✅ Saved: {output}[/green]")

    asyncio.run(_test())


@app.command()
def serve(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="設定ファイルパス（デフォルト: config/lobby.yaml）",
    ),
    host: str = typer.Option("0.0.0.0", "--host", help="バインドアドレス"),
    port: int = typer.Option(8100, "--port", "-p", help="ポート番号"),
):
    """バックエンドAPIサーバーを起動"""
    import uvicorn

    data = load_config(config_path)
    server_conf = data.get("server", {})
    actual_host = server_conf.get("host", host)
    actual_port = server_conf.get("port", port)

    console.print(f"[cyan]Starting Lobby API server on {actual_host}:{actual_port}[/cyan]")

    from .api.main import app as api_app
    uvicorn.run(api_app, host=actual_host, port=actual_port)


@app.command()
def version():
    """バージョン表示"""
    from . import __version__
    console.print(f"Lobby v{__version__}")


def main():
    """エントリーポイント"""
    app()


if __name__ == "__main__":
    main()
