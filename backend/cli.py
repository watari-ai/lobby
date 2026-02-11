"""Lobby CLI - コマンドラインインターフェース"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .core.tts import TTSConfig, TTSClient
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
    output_dir: Path = typer.Option(
        Path("./output"),
        "--output", "-o",
        help="出力ディレクトリ",
    ),
    tts_url: str = typer.Option(
        "http://localhost:8880/v1",
        "--tts-url",
        help="TTS APIのベースURL",
    ),
    voice: str = typer.Option(
        "Vivian",
        "--voice", "-v",
        help="使用する音声（Vivian, Ryan, Serena等）",
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
        
        # TTS設定
        tts_config = TTSConfig(
            base_url=tts_url,
            voice=voice,
        )
        
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
        
        console.print(f"[green]✅ Recording complete![/green]")
        console.print(f"   Output: {output_dir / script.title.replace(' ', '_')}")
    
    asyncio.run(_record())


@app.command()
def tts_test(
    text: str = typer.Argument("おはロビィ！僕、倉土ロビィっす！", help="テストするテキスト"),
    output: Path = typer.Option(
        Path("./test_output.mp3"),
        "--output", "-o",
        help="出力ファイルパス",
    ),
    tts_url: str = typer.Option(
        "http://localhost:8880/v1",
        "--tts-url",
        help="TTS APIのベースURL",
    ),
    voice: str = typer.Option(
        "Vivian",
        "--voice", "-v",
        help="使用する音声",
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
def version():
    """バージョン表示"""
    from . import __version__
    console.print(f"Lobby v{__version__}")


def main():
    """エントリーポイント"""
    app()


if __name__ == "__main__":
    main()
