"""
BGM/SE Audio Manager for Lobby

Features:
- BGM playlist management with shuffle/repeat
- Sound effect triggers (mapped to emotions/reactions)
- Volume control with auto-ducking during speech
- Fade in/out support
- Multiple audio channels (BGM, SE, Voice)
"""

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from loguru import logger


class AudioChannel(Enum):
    """Audio channel types"""
    BGM = "bgm"
    SE = "se"
    VOICE = "voice"


class PlaybackState(Enum):
    """Playback state"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    FADING = "fading"


class RepeatMode(Enum):
    """Playlist repeat mode"""
    NONE = "none"
    ONE = "one"
    ALL = "all"


@dataclass
class AudioTrack:
    """Audio track information"""
    id: str
    path: Path
    name: str
    duration: float = 0.0  # seconds
    volume: float = 1.0  # 0.0 - 1.0
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": str(self.path),
            "name": self.name,
            "duration": self.duration,
            "volume": self.volume,
            "tags": self.tags,
        }


@dataclass
class SoundEffect:
    """Sound effect definition"""
    id: str
    path: Path
    name: str
    trigger: str  # emotion, action, or custom trigger
    volume: float = 1.0
    cooldown: float = 0.5  # seconds between plays
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": str(self.path),
            "name": self.name,
            "trigger": self.trigger,
            "volume": self.volume,
            "cooldown": self.cooldown,
        }


@dataclass
class ChannelState:
    """State of an audio channel"""
    channel: AudioChannel
    state: PlaybackState = PlaybackState.STOPPED
    current_track: AudioTrack | None = None
    volume: float = 1.0  # Master volume for this channel
    muted: bool = False
    position: float = 0.0  # Current playback position in seconds
    
    def to_dict(self) -> dict:
        return {
            "channel": self.channel.value,
            "state": self.state.value,
            "current_track": self.current_track.to_dict() if self.current_track else None,
            "volume": self.volume,
            "muted": self.muted,
            "position": self.position,
        }


class AudioManager:
    """
    BGM/SE Audio Manager
    
    Manages background music playlists, sound effects,
    and audio ducking during voice output.
    """
    
    def __init__(
        self,
        bgm_dir: Path | str = "audio/bgm",
        se_dir: Path | str = "audio/se",
        auto_duck: bool = True,
        duck_volume: float = 0.3,
        duck_fade_time: float = 0.3,
    ):
        self.bgm_dir = Path(bgm_dir)
        self.se_dir = Path(se_dir)
        self.auto_duck = auto_duck
        self.duck_volume = duck_volume
        self.duck_fade_time = duck_fade_time
        
        # Playlists
        self.playlists: dict[str, list[AudioTrack]] = {}
        self.current_playlist: str | None = None
        self.playlist_index: int = 0
        self.shuffle: bool = False
        self.repeat: RepeatMode = RepeatMode.ALL
        
        # Sound effects
        self.sound_effects: dict[str, SoundEffect] = {}
        self.se_cooldowns: dict[str, float] = {}  # Last play time
        
        # Channel states
        self.channels: dict[AudioChannel, ChannelState] = {
            AudioChannel.BGM: ChannelState(AudioChannel.BGM),
            AudioChannel.SE: ChannelState(AudioChannel.SE),
            AudioChannel.VOICE: ChannelState(AudioChannel.VOICE),
        }
        
        # Ducking state
        self._is_ducking = False
        self._original_bgm_volume = 1.0
        
        # Callbacks
        self._on_track_change: list[Callable] = []
        self._on_se_play: list[Callable] = []
        
        logger.info(f"AudioManager initialized: bgm={bgm_dir}, se={se_dir}")
    
    # === Playlist Management ===
    
    def create_playlist(self, name: str, tracks: list[AudioTrack] | None = None) -> None:
        """Create a new playlist"""
        self.playlists[name] = tracks or []
        logger.info(f"Created playlist: {name} ({len(self.playlists[name])} tracks)")
    
    def add_to_playlist(self, playlist_name: str, track: AudioTrack) -> None:
        """Add track to playlist"""
        if playlist_name not in self.playlists:
            self.playlists[playlist_name] = []
        self.playlists[playlist_name].append(track)
        logger.debug(f"Added track to {playlist_name}: {track.name}")
    
    def remove_from_playlist(self, playlist_name: str, track_id: str) -> bool:
        """Remove track from playlist"""
        if playlist_name not in self.playlists:
            return False
        
        original_len = len(self.playlists[playlist_name])
        self.playlists[playlist_name] = [
            t for t in self.playlists[playlist_name] if t.id != track_id
        ]
        removed = len(self.playlists[playlist_name]) < original_len
        if removed:
            logger.debug(f"Removed track {track_id} from {playlist_name}")
        return removed
    
    def load_playlist_from_directory(self, name: str, directory: Path | str) -> int:
        """Load all audio files from a directory into a playlist"""
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0
        
        tracks = []
        audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}
        
        for file_path in sorted(directory.iterdir()):
            if file_path.suffix.lower() in audio_extensions:
                track = AudioTrack(
                    id=file_path.stem,
                    path=file_path,
                    name=file_path.stem.replace("_", " ").title(),
                )
                tracks.append(track)
        
        self.playlists[name] = tracks
        logger.info(f"Loaded {len(tracks)} tracks into playlist: {name}")
        return len(tracks)
    
    def select_playlist(self, name: str) -> bool:
        """Select active playlist"""
        if name not in self.playlists:
            logger.warning(f"Playlist not found: {name}")
            return False
        
        self.current_playlist = name
        self.playlist_index = 0
        logger.info(f"Selected playlist: {name}")
        return True
    
    def get_playlists(self) -> dict[str, list[dict]]:
        """Get all playlists with track info"""
        return {
            name: [t.to_dict() for t in tracks]
            for name, tracks in self.playlists.items()
        }
    
    # === BGM Playback Control ===
    
    async def play_bgm(self, track: AudioTrack | None = None) -> bool:
        """Start BGM playback"""
        channel = self.channels[AudioChannel.BGM]
        
        if track:
            channel.current_track = track
        elif self.current_playlist and self.playlists.get(self.current_playlist):
            playlist = self.playlists[self.current_playlist]
            if self.playlist_index < len(playlist):
                channel.current_track = playlist[self.playlist_index]
        
        if not channel.current_track:
            logger.warning("No track to play")
            return False
        
        channel.state = PlaybackState.PLAYING
        channel.position = 0.0
        
        # Notify callbacks
        for callback in self._on_track_change:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(channel.current_track)
                else:
                    callback(channel.current_track)
            except Exception as e:
                logger.error(f"Track change callback error: {e}")
        
        logger.info(f"Playing BGM: {channel.current_track.name}")
        return True
    
    async def pause_bgm(self) -> None:
        """Pause BGM playback"""
        channel = self.channels[AudioChannel.BGM]
        if channel.state == PlaybackState.PLAYING:
            channel.state = PlaybackState.PAUSED
            logger.info("BGM paused")
    
    async def resume_bgm(self) -> None:
        """Resume BGM playback"""
        channel = self.channels[AudioChannel.BGM]
        if channel.state == PlaybackState.PAUSED:
            channel.state = PlaybackState.PLAYING
            logger.info("BGM resumed")
    
    async def stop_bgm(self) -> None:
        """Stop BGM playback"""
        channel = self.channels[AudioChannel.BGM]
        channel.state = PlaybackState.STOPPED
        channel.position = 0.0
        logger.info("BGM stopped")
    
    async def next_track(self) -> bool:
        """Skip to next track in playlist"""
        if not self.current_playlist:
            return False
        
        playlist = self.playlists.get(self.current_playlist, [])
        if not playlist:
            return False
        
        if self.shuffle:
            import random
            self.playlist_index = random.randint(0, len(playlist) - 1)
        else:
            self.playlist_index += 1
            if self.playlist_index >= len(playlist):
                if self.repeat == RepeatMode.ALL:
                    self.playlist_index = 0
                else:
                    self.playlist_index = len(playlist) - 1
                    return False
        
        return await self.play_bgm()
    
    async def previous_track(self) -> bool:
        """Go to previous track in playlist"""
        if not self.current_playlist:
            return False
        
        playlist = self.playlists.get(self.current_playlist, [])
        if not playlist:
            return False
        
        self.playlist_index = max(0, self.playlist_index - 1)
        return await self.play_bgm()
    
    # === Sound Effects ===
    
    def register_se(self, se: SoundEffect) -> None:
        """Register a sound effect"""
        self.sound_effects[se.id] = se
        logger.debug(f"Registered SE: {se.id} (trigger: {se.trigger})")
    
    def load_se_from_directory(self, directory: Path | str | None = None) -> int:
        """Load sound effects from directory"""
        directory = Path(directory) if directory else self.se_dir
        if not directory.exists():
            logger.warning(f"SE directory not found: {directory}")
            return 0
        
        count = 0
        audio_extensions = {".mp3", ".wav", ".ogg"}
        
        for file_path in directory.iterdir():
            if file_path.suffix.lower() in audio_extensions:
                # Parse trigger from filename: emotion_happy.wav -> trigger="happy"
                name = file_path.stem
                parts = name.split("_")
                trigger = parts[-1] if len(parts) > 1 else name
                
                se = SoundEffect(
                    id=name,
                    path=file_path,
                    name=name.replace("_", " ").title(),
                    trigger=trigger,
                )
                self.register_se(se)
                count += 1
        
        logger.info(f"Loaded {count} sound effects from {directory}")
        return count
    
    async def play_se(self, se_id: str, force: bool = False) -> bool:
        """Play a sound effect"""
        if se_id not in self.sound_effects:
            logger.warning(f"SE not found: {se_id}")
            return False
        
        se = self.sound_effects[se_id]
        
        # Check cooldown
        import time
        now = time.time()
        last_play = self.se_cooldowns.get(se_id, 0)
        if not force and (now - last_play) < se.cooldown:
            logger.debug(f"SE on cooldown: {se_id}")
            return False
        
        self.se_cooldowns[se_id] = now
        
        channel = self.channels[AudioChannel.SE]
        channel.current_track = AudioTrack(
            id=se.id,
            path=se.path,
            name=se.name,
            volume=se.volume,
        )
        channel.state = PlaybackState.PLAYING
        
        # Notify callbacks
        for callback in self._on_se_play:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(se)
                else:
                    callback(se)
            except Exception as e:
                logger.error(f"SE play callback error: {e}")
        
        logger.debug(f"Playing SE: {se.name}")
        return True
    
    async def trigger_se(self, trigger: str) -> bool:
        """Play SE by trigger (emotion, action, etc.)"""
        for se in self.sound_effects.values():
            if se.trigger == trigger:
                return await self.play_se(se.id)
        return False
    
    def get_se_by_trigger(self, trigger: str) -> list[SoundEffect]:
        """Get all SEs matching a trigger"""
        return [se for se in self.sound_effects.values() if se.trigger == trigger]
    
    # === Volume Control ===
    
    def set_volume(self, channel: AudioChannel, volume: float) -> None:
        """Set channel volume (0.0 - 1.0)"""
        volume = max(0.0, min(1.0, volume))
        self.channels[channel].volume = volume
        logger.debug(f"Set {channel.value} volume: {volume:.2f}")
    
    def get_volume(self, channel: AudioChannel) -> float:
        """Get channel volume"""
        return self.channels[channel].volume
    
    def set_muted(self, channel: AudioChannel, muted: bool) -> None:
        """Mute/unmute channel"""
        self.channels[channel].muted = muted
        logger.debug(f"Set {channel.value} muted: {muted}")
    
    def is_muted(self, channel: AudioChannel) -> bool:
        """Check if channel is muted"""
        return self.channels[channel].muted
    
    # === Auto-Ducking ===
    
    async def start_ducking(self) -> None:
        """Start audio ducking (lower BGM volume during speech)"""
        if not self.auto_duck or self._is_ducking:
            return
        
        self._is_ducking = True
        self._original_bgm_volume = self.channels[AudioChannel.BGM].volume
        
        # Fade to duck volume
        target_volume = self._original_bgm_volume * self.duck_volume
        await self._fade_volume(AudioChannel.BGM, target_volume, self.duck_fade_time)
        logger.debug(f"Ducking started: {self._original_bgm_volume:.2f} -> {target_volume:.2f}")
    
    async def stop_ducking(self) -> None:
        """Stop audio ducking (restore BGM volume)"""
        if not self._is_ducking:
            return
        
        self._is_ducking = False
        
        # Fade back to original volume
        await self._fade_volume(
            AudioChannel.BGM, self._original_bgm_volume, self.duck_fade_time
        )
        logger.debug(f"Ducking stopped: restored to {self._original_bgm_volume:.2f}")
    
    async def _fade_volume(
        self, channel: AudioChannel, target: float, duration: float
    ) -> None:
        """Fade channel volume over time"""
        state = self.channels[channel]
        start_volume = state.volume
        steps = max(1, int(duration * 20))  # 20 steps per second
        step_time = duration / steps
        volume_step = (target - start_volume) / steps
        
        state.state = PlaybackState.FADING
        
        for i in range(steps):
            state.volume = start_volume + (volume_step * (i + 1))
            await asyncio.sleep(step_time)
        
        state.volume = target
        if state.state == PlaybackState.FADING:
            state.state = PlaybackState.PLAYING
    
    # === Callbacks ===
    
    def on_track_change(self, callback: Callable) -> None:
        """Register callback for track changes"""
        self._on_track_change.append(callback)
    
    def on_se_play(self, callback: Callable) -> None:
        """Register callback for SE plays"""
        self._on_se_play.append(callback)
    
    # === State ===
    
    def get_state(self) -> dict:
        """Get full audio manager state"""
        return {
            "channels": {
                ch.value: state.to_dict()
                for ch, state in self.channels.items()
            },
            "current_playlist": self.current_playlist,
            "playlist_index": self.playlist_index,
            "shuffle": self.shuffle,
            "repeat": self.repeat.value,
            "auto_duck": self.auto_duck,
            "is_ducking": self._is_ducking,
            "playlists": list(self.playlists.keys()),
            "sound_effects": list(self.sound_effects.keys()),
        }


# Default emotion -> SE mapping
EMOTION_SE_MAPPING = {
    "happy": ["se_happy", "chime_happy"],
    "excited": ["se_excited", "fanfare"],
    "sad": ["se_sad", "sigh"],
    "angry": ["se_angry", "growl"],
    "surprised": ["se_surprised", "gasp"],
    "confused": ["se_confused", "hmm"],
    "laughing": ["se_laugh", "giggle"],
}
