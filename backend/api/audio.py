"""
Audio API Routes for Lobby

Provides REST endpoints for BGM/SE management:
- Playlist CRUD
- Playback control
- Volume control
- Sound effect triggers
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.audio_manager import (
    AudioChannel,
    AudioManager,
    AudioTrack,
    RepeatMode,
    SoundEffect,
)

router = APIRouter(prefix="/audio", tags=["audio"])

# Global audio manager instance
_audio_manager: AudioManager | None = None


def get_audio_manager() -> AudioManager:
    """Get or create audio manager instance"""
    global _audio_manager
    if _audio_manager is None:
        _audio_manager = AudioManager()
    return _audio_manager


def set_audio_manager(manager: AudioManager) -> None:
    """Set audio manager instance (for testing)"""
    global _audio_manager
    _audio_manager = manager


# === Request/Response Models ===

class TrackCreate(BaseModel):
    """Create track request"""
    id: str
    path: str
    name: str
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class PlaylistCreate(BaseModel):
    """Create playlist request"""
    name: str
    tracks: list[TrackCreate] = Field(default_factory=list)


class PlaylistLoadRequest(BaseModel):
    """Load playlist from directory request"""
    name: str
    directory: str


class VolumeSet(BaseModel):
    """Volume set request"""
    channel: str = Field(..., pattern="^(bgm|se|voice)$")
    volume: float = Field(..., ge=0.0, le=1.0)


class MuteSet(BaseModel):
    """Mute set request"""
    channel: str = Field(..., pattern="^(bgm|se|voice)$")
    muted: bool


class SECreate(BaseModel):
    """Sound effect create request"""
    id: str
    path: str
    name: str
    trigger: str
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    cooldown: float = Field(default=0.5, ge=0.0)


class SEPlayRequest(BaseModel):
    """Sound effect play request"""
    se_id: str | None = None
    trigger: str | None = None
    force: bool = False


class DuckingConfig(BaseModel):
    """Ducking configuration"""
    enabled: bool = True
    duck_volume: float = Field(default=0.3, ge=0.0, le=1.0)
    fade_time: float = Field(default=0.3, ge=0.0)


class PlaybackSettings(BaseModel):
    """Playback settings"""
    shuffle: bool = False
    repeat: str = Field(default="all", pattern="^(none|one|all)$")


# === Status ===

@router.get("/status")
async def get_audio_status():
    """Get audio manager status"""
    manager = get_audio_manager()
    return manager.get_state()


# === Playlist Management ===

@router.get("/playlists")
async def list_playlists():
    """List all playlists"""
    manager = get_audio_manager()
    return {
        "playlists": manager.get_playlists(),
        "current": manager.current_playlist,
    }


@router.post("/playlists")
async def create_playlist(req: PlaylistCreate):
    """Create a new playlist"""
    manager = get_audio_manager()

    tracks = [
        AudioTrack(
            id=t.id,
            path=Path(t.path),
            name=t.name,
            volume=t.volume,
            tags=t.tags,
        )
        for t in req.tracks
    ]

    manager.create_playlist(req.name, tracks)

    return {
        "message": f"Playlist '{req.name}' created",
        "track_count": len(tracks),
    }


@router.post("/playlists/load")
async def load_playlist_from_directory(req: PlaylistLoadRequest):
    """Load playlist from a directory"""
    manager = get_audio_manager()

    directory = Path(req.directory)
    if not directory.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {req.directory}")

    count = manager.load_playlist_from_directory(req.name, directory)

    return {
        "message": f"Playlist '{req.name}' loaded",
        "track_count": count,
    }


@router.delete("/playlists/{name}")
async def delete_playlist(name: str):
    """Delete a playlist"""
    manager = get_audio_manager()

    if name not in manager.playlists:
        raise HTTPException(status_code=404, detail=f"Playlist not found: {name}")

    del manager.playlists[name]
    if manager.current_playlist == name:
        manager.current_playlist = None

    return {"message": f"Playlist '{name}' deleted"}


@router.post("/playlists/{name}/select")
async def select_playlist(name: str):
    """Select playlist for playback"""
    manager = get_audio_manager()

    if not manager.select_playlist(name):
        raise HTTPException(status_code=404, detail=f"Playlist not found: {name}")

    return {"message": f"Playlist '{name}' selected"}


@router.post("/playlists/{name}/tracks")
async def add_track_to_playlist(name: str, track: TrackCreate):
    """Add track to playlist"""
    manager = get_audio_manager()

    audio_track = AudioTrack(
        id=track.id,
        path=Path(track.path),
        name=track.name,
        volume=track.volume,
        tags=track.tags,
    )

    manager.add_to_playlist(name, audio_track)

    return {"message": f"Track '{track.name}' added to playlist '{name}'"}


@router.delete("/playlists/{name}/tracks/{track_id}")
async def remove_track_from_playlist(name: str, track_id: str):
    """Remove track from playlist"""
    manager = get_audio_manager()

    if not manager.remove_from_playlist(name, track_id):
        raise HTTPException(status_code=404, detail="Track not found")

    return {"message": f"Track '{track_id}' removed from playlist '{name}'"}


# === BGM Playback ===

@router.post("/bgm/play")
async def play_bgm(track_id: str | None = None):
    """Start BGM playback"""
    manager = get_audio_manager()

    track = None
    if track_id:
        # Find track in current playlist
        if manager.current_playlist:
            playlist = manager.playlists.get(manager.current_playlist, [])
            track = next((t for t in playlist if t.id == track_id), None)

        if not track:
            raise HTTPException(status_code=404, detail=f"Track not found: {track_id}")

    success = await manager.play_bgm(track)
    if not success:
        raise HTTPException(status_code=400, detail="No track to play")

    return {
        "message": "BGM playing",
        "track": manager.channels[AudioChannel.BGM].current_track.to_dict()
        if manager.channels[AudioChannel.BGM].current_track else None,
    }


@router.post("/bgm/pause")
async def pause_bgm():
    """Pause BGM playback"""
    manager = get_audio_manager()
    await manager.pause_bgm()
    return {"message": "BGM paused"}


@router.post("/bgm/resume")
async def resume_bgm():
    """Resume BGM playback"""
    manager = get_audio_manager()
    await manager.resume_bgm()
    return {"message": "BGM resumed"}


@router.post("/bgm/stop")
async def stop_bgm():
    """Stop BGM playback"""
    manager = get_audio_manager()
    await manager.stop_bgm()
    return {"message": "BGM stopped"}


@router.post("/bgm/next")
async def next_track():
    """Skip to next track"""
    manager = get_audio_manager()
    success = await manager.next_track()

    if not success:
        return {"message": "End of playlist"}

    return {
        "message": "Next track",
        "track": manager.channels[AudioChannel.BGM].current_track.to_dict()
        if manager.channels[AudioChannel.BGM].current_track else None,
    }


@router.post("/bgm/previous")
async def previous_track():
    """Go to previous track"""
    manager = get_audio_manager()
    await manager.previous_track()

    return {
        "message": "Previous track",
        "track": manager.channels[AudioChannel.BGM].current_track.to_dict()
        if manager.channels[AudioChannel.BGM].current_track else None,
    }


@router.put("/bgm/settings")
async def set_playback_settings(settings: PlaybackSettings):
    """Set playback settings (shuffle, repeat)"""
    manager = get_audio_manager()

    manager.shuffle = settings.shuffle
    manager.repeat = RepeatMode(settings.repeat)

    return {
        "shuffle": manager.shuffle,
        "repeat": manager.repeat.value,
    }


# === Sound Effects ===

@router.get("/se")
async def list_sound_effects():
    """List all registered sound effects"""
    manager = get_audio_manager()
    return {
        "sound_effects": [
            se.to_dict() for se in manager.sound_effects.values()
        ]
    }


@router.post("/se")
async def register_sound_effect(req: SECreate):
    """Register a sound effect"""
    manager = get_audio_manager()

    se = SoundEffect(
        id=req.id,
        path=Path(req.path),
        name=req.name,
        trigger=req.trigger,
        volume=req.volume,
        cooldown=req.cooldown,
    )

    manager.register_se(se)

    return {"message": f"Sound effect '{req.id}' registered"}


@router.post("/se/load")
async def load_sound_effects(directory: str | None = None):
    """Load sound effects from directory"""
    manager = get_audio_manager()

    dir_path = Path(directory) if directory else None
    count = manager.load_se_from_directory(dir_path)

    return {"message": f"Loaded {count} sound effects"}


@router.post("/se/play")
async def play_sound_effect(req: SEPlayRequest):
    """Play a sound effect by ID or trigger"""
    manager = get_audio_manager()

    if req.se_id:
        success = await manager.play_se(req.se_id, force=req.force)
    elif req.trigger:
        success = await manager.trigger_se(req.trigger)
    else:
        raise HTTPException(status_code=400, detail="Either se_id or trigger required")

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Sound effect not found or on cooldown",
        )

    return {"message": "Sound effect played"}


@router.delete("/se/{se_id}")
async def unregister_sound_effect(se_id: str):
    """Unregister a sound effect"""
    manager = get_audio_manager()

    if se_id not in manager.sound_effects:
        raise HTTPException(status_code=404, detail=f"Sound effect not found: {se_id}")

    del manager.sound_effects[se_id]
    return {"message": f"Sound effect '{se_id}' unregistered"}


# === Volume Control ===

@router.get("/volume")
async def get_all_volumes():
    """Get all channel volumes"""
    manager = get_audio_manager()
    return {
        "volumes": {
            ch.value: {
                "volume": state.volume,
                "muted": state.muted,
            }
            for ch, state in manager.channels.items()
        }
    }


@router.put("/volume")
async def set_volume(req: VolumeSet):
    """Set channel volume"""
    manager = get_audio_manager()
    channel = AudioChannel(req.channel)
    manager.set_volume(channel, req.volume)
    return {"channel": req.channel, "volume": req.volume}


@router.put("/mute")
async def set_mute(req: MuteSet):
    """Set channel mute state"""
    manager = get_audio_manager()
    channel = AudioChannel(req.channel)
    manager.set_muted(channel, req.muted)
    return {"channel": req.channel, "muted": req.muted}


# === Ducking ===

@router.get("/ducking")
async def get_ducking_config():
    """Get ducking configuration"""
    manager = get_audio_manager()
    return {
        "enabled": manager.auto_duck,
        "duck_volume": manager.duck_volume,
        "fade_time": manager.duck_fade_time,
        "is_ducking": manager._is_ducking,
    }


@router.put("/ducking")
async def set_ducking_config(config: DuckingConfig):
    """Set ducking configuration"""
    manager = get_audio_manager()
    manager.auto_duck = config.enabled
    manager.duck_volume = config.duck_volume
    manager.duck_fade_time = config.fade_time
    return {
        "enabled": manager.auto_duck,
        "duck_volume": manager.duck_volume,
        "fade_time": manager.duck_fade_time,
    }


@router.post("/ducking/start")
async def start_ducking():
    """Manually start ducking"""
    manager = get_audio_manager()
    await manager.start_ducking()
    return {"message": "Ducking started"}


@router.post("/ducking/stop")
async def stop_ducking():
    """Manually stop ducking"""
    manager = get_audio_manager()
    await manager.stop_ducking()
    return {"message": "Ducking stopped"}
