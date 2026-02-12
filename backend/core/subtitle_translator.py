"""Subtitle Translator - 多言語字幕翻訳"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from .subtitle import SubtitleEntry, SubtitleFormat, SubtitleTrack


class TranslationProvider(str, Enum):
    """翻訳プロバイダー"""
    OPENCLAW = "openclaw"  # OpenClaw Gateway (LLM)
    DEEPL = "deepl"        # DeepL API
    GOOGLE = "google"      # Google Translate


# 言語コードと名前のマッピング
LANGUAGE_NAMES = {
    "ja": "Japanese",
    "en": "English",
    "zh": "Chinese",
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
}


@dataclass
class TranslatorConfig:
    """翻訳設定"""
    provider: TranslationProvider = TranslationProvider.OPENCLAW
    
    # OpenClaw設定
    openclaw_url: str = "http://localhost:18789"
    openclaw_model: str = ""  # 空=Gateway デフォルト
    
    # DeepL設定（オプション）
    deepl_api_key: str = ""
    
    # 翻訳オプション
    batch_size: int = 10  # バッチ翻訳のサイズ
    preserve_timing: bool = True  # タイミングを保持
    preserve_style: bool = True  # スタイル指定を保持
    
    # 品質オプション
    context_lines: int = 2  # 前後の文脈行数
    formal: bool = False  # フォーマルな表現を使用


@dataclass
class TranslationResult:
    """翻訳結果"""
    original: str
    translated: str
    source_lang: str
    target_lang: str
    confidence: float = 1.0


class SubtitleTranslator:
    """字幕翻訳器
    
    OpenClaw Gateway経由で字幕を多言語に翻訳。
    LLMを使った高品質な翻訳を実現。
    """
    
    def __init__(self, config: Optional[TranslatorConfig] = None):
        self.config = config or TranslatorConfig()
        self._client: Optional[httpx.AsyncClient] = None
        
    async def _get_client(self) -> httpx.AsyncClient:
        """HTTPクライアント取得"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
    
    async def close(self):
        """クライアントクローズ"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_language_name(self, code: str) -> str:
        """言語コードから言語名を取得"""
        return LANGUAGE_NAMES.get(code, code)
    
    async def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[list[str]] = None,
    ) -> TranslationResult:
        """テキストを翻訳
        
        Args:
            text: 翻訳するテキスト
            source_lang: 元言語コード（"ja", "en"等）
            target_lang: 翻訳先言語コード
            context: 前後の文脈（オプション）
            
        Returns:
            TranslationResult
        """
        if self.config.provider == TranslationProvider.OPENCLAW:
            return await self._translate_with_openclaw(
                text, source_lang, target_lang, context
            )
        elif self.config.provider == TranslationProvider.DEEPL:
            return await self._translate_with_deepl(
                text, source_lang, target_lang
            )
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    async def _translate_with_openclaw(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[list[str]] = None,
    ) -> TranslationResult:
        """OpenClaw経由でLLM翻訳"""
        client = await self._get_client()
        
        source_name = self._get_language_name(source_lang)
        target_name = self._get_language_name(target_lang)
        
        # 翻訳プロンプト構築
        system_prompt = f"""You are a professional subtitle translator.
Translate the following {source_name} subtitle text to {target_name}.

IMPORTANT RULES:
- Translate ONLY the text, preserving the original meaning and tone
- Keep the translation natural and conversational for subtitles
- Maintain any speaker characteristics or style
- Do NOT add explanations or notes
- Return ONLY the translated text, nothing else
{"- Use formal language" if self.config.formal else "- Use casual/natural language"}"""

        # 文脈があれば追加
        user_content = text
        if context:
            context_text = "\n".join(f"[Context: {c}]" for c in context if c)
            if context_text:
                user_content = f"{context_text}\n\n[Translate this]: {text}"
        
        try:
            response = await client.post(
                f"{self.config.openclaw_url}/v1/chat/completions",
                json={
                    "model": self.config.openclaw_model or "default",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,  # 翻訳は低temperatureで
                },
            )
            response.raise_for_status()
            
            data = response.json()
            translated = data["choices"][0]["message"]["content"].strip()
            
            # 余分な引用符やフォーマットを除去
            translated = self._clean_translation(translated)
            
            return TranslationResult(
                original=text,
                translated=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=1.0,
            )
            
        except Exception as e:
            logger.error(f"OpenClaw translation failed: {e}")
            # フォールバック: 元のテキストを返す
            return TranslationResult(
                original=text,
                translated=text,
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=0.0,
            )
    
    async def _translate_with_deepl(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        """DeepL API経由で翻訳"""
        if not self.config.deepl_api_key:
            raise ValueError("DeepL API key not configured")
        
        client = await self._get_client()
        
        # DeepL言語コード変換
        deepl_source = source_lang.upper()
        deepl_target = target_lang.upper()
        if deepl_target == "EN":
            deepl_target = "EN-US"
        
        try:
            response = await client.post(
                "https://api-free.deepl.com/v2/translate",
                headers={"Authorization": f"DeepL-Auth-Key {self.config.deepl_api_key}"},
                data={
                    "text": text,
                    "source_lang": deepl_source,
                    "target_lang": deepl_target,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            translated = data["translations"][0]["text"]
            
            return TranslationResult(
                original=text,
                translated=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=1.0,
            )
            
        except Exception as e:
            logger.error(f"DeepL translation failed: {e}")
            return TranslationResult(
                original=text,
                translated=text,
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=0.0,
            )
    
    def _clean_translation(self, text: str) -> str:
        """翻訳結果のクリーニング"""
        # 引用符で囲まれている場合は除去
        if (text.startswith('"') and text.endswith('"')) or \
           (text.startswith("'") and text.endswith("'")):
            text = text[1:-1]
        
        # "Translation:" などのプレフィックスを除去
        prefixes = ["Translation:", "Translated:", "[Translation]", "[Translate]"]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        return text.strip()
    
    async def translate_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
    ) -> list[TranslationResult]:
        """バッチ翻訳（効率的な複数テキスト翻訳）
        
        Args:
            texts: 翻訳するテキストリスト
            source_lang: 元言語
            target_lang: 翻訳先言語
            
        Returns:
            TranslationResultのリスト
        """
        results = []
        
        # 文脈を考慮してバッチ処理
        for i, text in enumerate(texts):
            # 前後の文脈を取得
            context = []
            if self.config.context_lines > 0:
                start = max(0, i - self.config.context_lines)
                end = min(len(texts), i + self.config.context_lines + 1)
                context = [texts[j] for j in range(start, end) if j != i]
            
            result = await self.translate_text(
                text, source_lang, target_lang, context
            )
            results.append(result)
            
            # レート制限対策
            if i > 0 and i % self.config.batch_size == 0:
                await asyncio.sleep(0.5)
        
        return results
    
    async def translate_track(
        self,
        track: SubtitleTrack,
        target_lang: str,
        title_suffix: Optional[str] = None,
    ) -> SubtitleTrack:
        """字幕トラック全体を翻訳
        
        Args:
            track: 翻訳元の字幕トラック
            target_lang: 翻訳先言語コード
            title_suffix: タイトルに追加するサフィックス
            
        Returns:
            翻訳された新しいSubtitleTrack
        """
        source_lang = track.language
        logger.info(
            f"Translating {len(track.entries)} entries: "
            f"{source_lang} -> {target_lang}"
        )
        
        # 翻訳対象テキストを抽出
        texts = [entry.text for entry in track.entries]
        
        # バッチ翻訳実行
        translations = await self.translate_batch(texts, source_lang, target_lang)
        
        # 新しいトラック作成
        new_title = track.title
        if new_title and title_suffix:
            new_title = f"{new_title} ({title_suffix})"
        elif new_title:
            new_title = f"{new_title} ({self._get_language_name(target_lang)})"
        
        translated_track = SubtitleTrack(
            title=new_title,
            language=target_lang,
        )
        
        # エントリーをコピー＆翻訳テキスト適用
        for i, entry in enumerate(track.entries):
            translated_track.entries.append(
                SubtitleEntry(
                    index=entry.index,
                    start_ms=entry.start_ms,
                    end_ms=entry.end_ms,
                    text=translations[i].translated,
                    speaker=entry.speaker,
                    style=entry.style if self.config.preserve_style else None,
                )
            )
        
        success_count = sum(1 for t in translations if t.confidence > 0)
        logger.info(
            f"Translation complete: {success_count}/{len(translations)} successful"
        )
        
        return translated_track


async def translate_subtitle_file(
    input_path: Path,
    target_langs: list[str],
    output_dir: Optional[Path] = None,
    config: Optional[TranslatorConfig] = None,
) -> dict[str, Path]:
    """字幕ファイルを複数言語に翻訳
    
    Args:
        input_path: 入力字幕ファイル（.srt or .vtt）
        target_langs: 翻訳先言語コードのリスト
        output_dir: 出力ディレクトリ（デフォルト: 入力と同じ）
        config: 翻訳設定
        
    Returns:
        {lang_code: output_path} の辞書
    """
    from .subtitle import SubtitleFormat
    
    if output_dir is None:
        output_dir = input_path.parent
    
    # 入力ファイル読み込み
    content = input_path.read_text(encoding="utf-8")
    source_format = SubtitleFormat.VTT if input_path.suffix.lower() == ".vtt" else SubtitleFormat.SRT
    
    # パース
    track = _parse_subtitle_file(content, source_format)
    
    # 翻訳実行
    translator = SubtitleTranslator(config)
    output_paths = {}
    
    try:
        for lang in target_langs:
            logger.info(f"Translating to {lang}...")
            translated = await translator.translate_track(track, lang)
            
            # 出力ファイル名
            stem = input_path.stem
            output_path = output_dir / f"{stem}.{lang}{input_path.suffix}"
            
            translated.save(output_path, source_format)
            output_paths[lang] = output_path
            
            logger.info(f"Saved: {output_path}")
    
    finally:
        await translator.close()
    
    return output_paths


def _parse_subtitle_file(content: str, format: SubtitleFormat) -> SubtitleTrack:
    """字幕ファイルをパース"""
    track = SubtitleTrack()
    
    if format == SubtitleFormat.VTT:
        return _parse_vtt(content, track)
    else:
        return _parse_srt(content, track)


def _parse_srt(content: str, track: SubtitleTrack) -> SubtitleTrack:
    """SRTファイルをパース"""
    blocks = content.strip().split("\n\n")
    
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        
        try:
            # インデックス行をスキップ
            time_line = lines[1]
            text = "\n".join(lines[2:])
            
            # タイムスタンプパース
            start_str, end_str = time_line.split(" --> ")
            start_ms = _srt_time_to_ms(start_str.strip())
            end_ms = _srt_time_to_ms(end_str.strip())
            
            track.add_entry(text=text, start_ms=start_ms, end_ms=end_ms)
            
        except Exception as e:
            logger.warning(f"Failed to parse SRT block: {e}")
            continue
    
    return track


def _parse_vtt(content: str, track: SubtitleTrack) -> SubtitleTrack:
    """VTTファイルをパース"""
    lines = content.split("\n")
    
    # ヘッダーをスキップ
    i = 0
    while i < len(lines) and not "-->" in lines[i]:
        # 言語情報を抽出
        if lines[i].startswith("Language:"):
            track.language = lines[i].split(":")[1].strip()
        i += 1
    
    # キューをパース
    while i < len(lines):
        line = lines[i].strip()
        
        if "-->" in line:
            # タイムスタンプ行
            parts = line.split("-->")
            start_ms = _vtt_time_to_ms(parts[0].strip())
            end_ms = _vtt_time_to_ms(parts[1].strip().split()[0])
            
            # テキスト収集
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1
            
            text = "\n".join(text_lines)
            
            # VTTタグを除去
            if text.startswith("<v "):
                # <v Speaker>text の形式
                end_tag = text.find(">")
                if end_tag > 0:
                    text = text[end_tag + 1:]
            
            track.add_entry(text=text, start_ms=start_ms, end_ms=end_ms)
        
        i += 1
    
    return track


def _srt_time_to_ms(time_str: str) -> int:
    """SRTタイムスタンプをミリ秒に変換"""
    parts = time_str.replace(",", ":").split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    ms = int(parts[3]) if len(parts) > 3 else 0
    
    return (hours * 3600 + minutes * 60 + seconds) * 1000 + ms


def _vtt_time_to_ms(time_str: str) -> int:
    """VTTタイムスタンプをミリ秒に変換"""
    parts = time_str.replace(".", ":").split(":")
    if len(parts) == 3:
        # MM:SS.mmm
        minutes = int(parts[0])
        seconds = int(parts[1])
        ms = int(parts[2])
        return (minutes * 60 + seconds) * 1000 + ms
    else:
        # HH:MM:SS.mmm
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        ms = int(parts[3]) if len(parts) > 3 else 0
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + ms
