"""Lobby CLI - コマンドラインインターフェース"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .core.avatar import AvatarParts, LipsyncConfig
from .core.config import build_pipeline_config, build_tts_config, load_config
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
def validate(
    script_path: Path = typer.Argument(..., help="台本ファイルパス (.txt, .json)"),
    verbose: bool = typer.Option(False, "--verbose", "-V", help="各行の詳細を表示"),
):
    """台本をバリデーション＆プレビュー（収録前の確認用）"""
    from collections import Counter

    from .core.emotion import Emotion

    if not script_path.exists():
        console.print(f"[red]Error: Script not found: {script_path}[/red]")
        raise typer.Exit(1)

    try:
        script = Script.from_file(script_path)
    except Exception as e:
        console.print(f"[red]Error parsing script: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]台本プレビュー: {script.title}[/bold cyan]\n")

    # 基本情報
    total_lines = len(script.lines)
    total_chars = sum(len(line.text) for line in script.lines)
    total_wait = sum(line.wait_after for line in script.lines)

    # 推定再生時間（日本語: ~7文字/秒 + 待機時間）
    chars_per_sec = 7.0
    estimated_speech_sec = total_chars / chars_per_sec
    estimated_total_sec = estimated_speech_sec + total_wait
    est_min = int(estimated_total_sec // 60)
    est_sec = int(estimated_total_sec % 60)

    console.print(f"  行数: [bold]{total_lines}[/bold]")
    console.print(f"  文字数: [bold]{total_chars}[/bold]")
    console.print(f"  推定再生時間: [bold]{est_min}:{est_sec:02d}[/bold] (約{total_chars / chars_per_sec:.0f}秒 + 待機{total_wait:.1f}秒)")

    # 感情分布
    emotion_counts: Counter = Counter()
    for line in script.lines:
        emotion_counts[line.emotion.value] += 1

    console.print("\n[bold]感情分布:[/bold]")
    for emotion, count in emotion_counts.most_common():
        bar = "█" * count
        console.print(f"  {emotion:12s} {bar} ({count})")

    # 警告チェック
    warnings = []
    for i, line in enumerate(script.lines, 1):
        if len(line.text) > 200:
            warnings.append(f"行{i}: 長すぎ ({len(line.text)}文字) — TTS品質低下の可能性")
        if len(line.text) < 2:
            warnings.append(f"行{i}: 短すぎ ({len(line.text)}文字)")
        if line.emotion == Emotion.NEUTRAL and any(
            c in line.text for c in "！!？?♪"
        ):
            warnings.append(f"行{i}: 感情タグなし但し感嘆符あり — タグ付け推奨")

    if warnings:
        console.print(f"\n[yellow]⚠ 警告 ({len(warnings)}):[/yellow]")
        for w in warnings:
            console.print(f"  [yellow]- {w}[/yellow]")

    # 詳細表示
    if verbose:
        console.print("\n[bold]全行:[/bold]")
        for i, line in enumerate(script.lines, 1):
            emotion_tag = f"[{line.emotion.value}]" if line.emotion != Emotion.NEUTRAL else ""
            gesture_tag = f" 🤚{line.gesture}" if line.gesture else ""
            console.print(f"  {i:3d}. {emotion_tag:12s} {line.text[:60]}{gesture_tag}")

    console.print("\n[green]✅ バリデーション完了[/green]")


@app.command()
def doctor(
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="設定ファイルパス（lobby.yaml）",
    ),
):
    """環境診断 — 依存ツール・サーバーの状態を一括チェック"""
    import shutil
    import subprocess
    import sys

    import httpx

    from .core.config import load_config

    ok_count = 0
    warn_count = 0
    fail_count = 0

    def _ok(msg: str):
        nonlocal ok_count
        ok_count += 1
        console.print(f"  [green]✓[/green] {msg}")

    def _warn(msg: str):
        nonlocal warn_count
        warn_count += 1
        console.print(f"  [yellow]⚠[/yellow] {msg}")

    def _fail(msg: str):
        nonlocal fail_count
        fail_count += 1
        console.print(f"  [red]✗[/red] {msg}")

    console.print("[bold cyan]Lobby Doctor — 環境診断[/bold cyan]\n")

    # --- Python ---
    console.print("[bold]Python[/bold]")
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        _ok(f"Python {py_ver}")
    else:
        _fail(f"Python {py_ver} (3.11+ required)")

    # --- ffmpeg / ffprobe ---
    console.print("\n[bold]FFmpeg[/bold]")
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if path:
            try:
                ver = subprocess.check_output(
                    [tool, "-version"], stderr=subprocess.STDOUT, text=True,
                ).split("\n")[0]
                _ok(f"{tool}: {ver}")
            except Exception:
                _ok(f"{tool}: found at {path}")
        else:
            _fail(f"{tool} not found — install via: brew install ffmpeg")

    # --- Config ---
    console.print("\n[bold]Config[/bold]")
    data: dict = {}
    cfg_file = config_path or Path("config/lobby.yaml")
    if cfg_file.exists():
        _ok(f"Config: {cfg_file}")
        data = load_config(cfg_file)
    else:
        _warn(f"Config not found: {cfg_file}")

    # --- TTS server ---
    console.print("\n[bold]TTS Server[/bold]")
    tts_conf = data.get("tts", {})
    tts_url = tts_conf.get("base_url", "http://localhost:8001")
    tts_voice = tts_conf.get("voice", "lobby")
    try:
        r = httpx.get(f"{tts_url.rstrip('/').removesuffix('/v1')}/health", timeout=3)
        if r.status_code == 200:
            _ok(f"TTS reachable: {tts_url} (voice: {tts_voice})")
        else:
            _warn(f"TTS responded {r.status_code}: {tts_url}")
    except httpx.ConnectError:
        _warn(f"TTS not running: {tts_url}")
    except Exception as e:
        _warn(f"TTS check failed: {e}")

    # --- Frontend ---
    console.print("\n[bold]Frontend[/bold]")
    fe_dir = Path("frontend")
    if (fe_dir / "node_modules").exists():
        _ok("node_modules installed")
    elif fe_dir.exists():
        _warn("node_modules missing — run: cd frontend && pnpm install")
    else:
        _warn("frontend/ directory not found")

    if shutil.which("pnpm"):
        _ok("pnpm available")
    else:
        _warn("pnpm not found — install: npm i -g pnpm")

    # --- Models directory ---
    console.print("\n[bold]Models[/bold]")
    models_dir = Path("models")
    if models_dir.exists():
        model_files = list(models_dir.glob("*"))
        if model_files:
            _ok(f"models/ contains {len(model_files)} item(s)")
        else:
            _warn("models/ is empty — add avatar assets")
    else:
        _warn("models/ not found")

    # --- Summary ---
    console.print()
    total = ok_count + warn_count + fail_count
    console.print(f"[bold]Result: {ok_count}/{total} OK", end="")
    if warn_count:
        console.print(f", [yellow]{warn_count} warning(s)[/yellow]", end="")
    if fail_count:
        console.print(f", [red]{fail_count} error(s)[/red]", end="")
    console.print("[/bold]")

    if fail_count:
        raise typer.Exit(1)


@app.command()
def export(
    output_dir: Path = typer.Argument(..., help="収録出力ディレクトリ（record-videoの出力先）"),
    export_dir: Optional[Path] = typer.Option(
        None,
        "--to", "-t",
        help="エクスポート先（デフォルト: output_dir/export/）",
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        help="動画タイトル（デフォルト: ディレクトリ名）",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description", "-d",
        help="動画の説明文",
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        help="カンマ区切りのタグ",
    ),
    include_srt: bool = typer.Option(True, "--srt/--no-srt", help="SRT字幕を含める"),
    include_vtt: bool = typer.Option(False, "--vtt/--no-vtt", help="VTT字幕を含める"),
):
    """収録出力をYouTubeアップロード用にパッケージ化

    動画・字幕・メタデータをまとめてエクスポートフォルダに出力します。

    使い方:
      lobby export output/自己紹介 --title "ロビィ自己紹介" --tags "VTuber,AI"
    """
    import json
    import shutil
    from datetime import datetime, timezone

    if not output_dir.exists():
        console.print(f"[red]Error: Directory not found: {output_dir}[/red]")
        raise typer.Exit(1)

    # 動画ファイルを探す
    video_files = list(output_dir.glob("*.mp4"))
    if not video_files:
        console.print(f"[red]Error: No .mp4 files found in {output_dir}[/red]")
        raise typer.Exit(1)

    video_file = video_files[0]
    video_title = title or output_dir.name.replace("_", " ")
    dest = export_dir or (output_dir / "export")
    dest.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]エクスポート: {video_title}[/bold cyan]\n")

    # 動画コピー
    dest_video = dest / video_file.name
    shutil.copy2(video_file, dest_video)
    console.print(f"  [green]✓[/green] {video_file.name}")

    # 字幕コピー
    copied_subs = []
    if include_srt:
        for srt in output_dir.glob("*.srt"):
            shutil.copy2(srt, dest / srt.name)
            copied_subs.append(srt.name)
            console.print(f"  [green]✓[/green] {srt.name}")
    if include_vtt:
        for vtt in output_dir.glob("*.vtt"):
            shutil.copy2(vtt, dest / vtt.name)
            copied_subs.append(vtt.name)
            console.print(f"  [green]✓[/green] {vtt.name}")

    # サムネイル
    for thumb in output_dir.glob("thumbnail*"):
        shutil.copy2(thumb, dest / thumb.name)
        console.print(f"  [green]✓[/green] {thumb.name}")

    # 動画ファイルサイズ
    size_mb = dest_video.stat().st_size / (1024 * 1024)

    # メタデータJSON
    tag_list = [t.strip() for t in tags.split(",")] if tags else ["VTuber", "AI", "Lobby"]
    metadata = {
        "title": video_title,
        "description": description or f"{video_title} — Lobby AI VTuberで制作",
        "tags": tag_list,
        "video": video_file.name,
        "subtitles": copied_subs,
        "file_size_mb": round(size_mb, 1),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "generator": "Lobby AI VTuber",
    }
    meta_path = dest / "metadata.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"  [green]✓[/green] metadata.json")

    # 説明文テキスト
    desc_text = metadata["description"] + "\n\n"
    desc_text += f"Tags: {', '.join(tag_list)}\n"
    desc_text += f"Made with Lobby — https://github.com/watari-ai/lobby\n"
    desc_path = dest / "description.txt"
    desc_path.write_text(desc_text, encoding="utf-8")
    console.print(f"  [green]✓[/green] description.txt")

    file_count = len(list(dest.iterdir()))
    console.print(f"\n[green]✅ エクスポート完了！[/green]")
    console.print(f"   {dest} ({file_count} files, {size_mb:.1f} MB)")


@app.command()
def init(
    project_dir: Path = typer.Argument(
        Path("."),
        help="プロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="プロジェクト名（デフォルト: ディレクトリ名）",
    ),
):
    """新規プロジェクトをセットアップ（設定・ディレクトリ・サンプル台本を生成）"""
    import shutil
    import textwrap

    project_dir = project_dir.resolve()
    project_name = name or project_dir.name

    console.print(f"[bold cyan]Lobby プロジェクト初期化: {project_name}[/bold cyan]\n")

    # ディレクトリ作成
    dirs = ["scripts", "models", "output", "config"]
    for d in dirs:
        (project_dir / d).mkdir(parents=True, exist_ok=True)
        console.print(f"  [green]✓[/green] {d}/")

    # 設定ファイル
    config_file = project_dir / "config" / "lobby.yaml"
    if not config_file.exists():
        config_file.write_text(textwrap.dedent(f"""\
            # Lobby設定 — {project_name}
            # ドキュメント: https://github.com/watari-ai/lobby/blob/main/docs/GETTING_STARTED.md

            server:
              host: "0.0.0.0"
              port: 8100

            tts:
              provider: miotts        # miotts | qwen3-tts | openai
              base_url: http://localhost:8001
              voice: lobby
              response_format: base64

              emotion_prompts:
                happy: "明るく楽しそうに"
                sad: "しんみりと悲しげに"
                excited: "テンション高く興奮して"
                angry: "怒った声で"
                surprised: "驚いた声で"
                neutral: ""

            avatar:
              base: ""               # models/にアバター画像を配置
              mouth_closed: ""
              mouth_open_s: ""

            lipsync:
              fps: 30
              mouth_sensitivity: 0.5
              blink_interval_ms: 3000

            video:
              fps: 30
              width: 1920
              height: 1080
              codec: libx264
              crf: 23
              preset: medium

            subtitle:
              enabled: true
              burn_in: false
              formats:
                - srt

            bgm:
              enabled: false

            output_dir: ./output
        """), encoding="utf-8")
        console.print(f"  [green]✓[/green] config/lobby.yaml")
    else:
        console.print(f"  [yellow]⏭[/yellow] config/lobby.yaml (already exists)")

    # サンプル台本
    sample_script = project_dir / "scripts" / "sample.txt"
    if not sample_script.exists():
        sample_script.write_text(textwrap.dedent("""\
            おはロビィ！僕、倉土ロビィっす！
            [excited] 今日はみんなに自己紹介するっす！
            [happy] よろしくお願いしますっす！
        """), encoding="utf-8")
        console.print(f"  [green]✓[/green] scripts/sample.txt")
    else:
        console.print(f"  [yellow]⏭[/yellow] scripts/sample.txt (already exists)")

    # .gitignore
    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("output/\n*.mp3\n*.mp4\n*.wav\n.DS_Store\n", encoding="utf-8")
        console.print(f"  [green]✓[/green] .gitignore")

    console.print(f"\n[green]✅ プロジェクト初期化完了！[/green]")
    console.print(f"\n[bold]次のステップ:[/bold]")
    console.print(f"  1. models/ にアバター画像を配置")
    console.print(f"  2. config/lobby.yaml を編集")
    console.print(f"  3. lobby doctor --config config/lobby.yaml で環境チェック")
    console.print(f"  4. lobby record-video scripts/sample.txt --config config/lobby.yaml")


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
