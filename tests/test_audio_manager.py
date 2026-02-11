"""Tests for Audio Manager"""

import asyncio
from pathlib import Path

import pytest

from backend.core.audio_manager import (
    AudioChannel,
    AudioManager,
    AudioTrack,
    PlaybackState,
    RepeatMode,
    SoundEffect,
)


@pytest.fixture
def audio_manager():
    """Create audio manager instance"""
    return AudioManager()


@pytest.fixture
def sample_tracks():
    """Create sample audio tracks"""
    return [
        AudioTrack(
            id="track1",
            path=Path("audio/bgm/track1.mp3"),
            name="Track One",
            duration=180.0,
        ),
        AudioTrack(
            id="track2",
            path=Path("audio/bgm/track2.mp3"),
            name="Track Two",
            duration=240.0,
        ),
        AudioTrack(
            id="track3",
            path=Path("audio/bgm/track3.mp3"),
            name="Track Three",
            duration=200.0,
        ),
    ]


@pytest.fixture
def sample_se():
    """Create sample sound effect"""
    return SoundEffect(
        id="se_happy",
        path=Path("audio/se/happy.wav"),
        name="Happy Sound",
        trigger="happy",
        volume=0.8,
        cooldown=0.5,
    )


class TestPlaylistManagement:
    """Test playlist management functions"""
    
    def test_create_playlist(self, audio_manager, sample_tracks):
        """Test creating a playlist"""
        audio_manager.create_playlist("test", sample_tracks)
        
        assert "test" in audio_manager.playlists
        assert len(audio_manager.playlists["test"]) == 3
    
    def test_create_empty_playlist(self, audio_manager):
        """Test creating an empty playlist"""
        audio_manager.create_playlist("empty")
        
        assert "empty" in audio_manager.playlists
        assert len(audio_manager.playlists["empty"]) == 0
    
    def test_add_to_playlist(self, audio_manager, sample_tracks):
        """Test adding track to playlist"""
        audio_manager.create_playlist("test")
        audio_manager.add_to_playlist("test", sample_tracks[0])
        
        assert len(audio_manager.playlists["test"]) == 1
        assert audio_manager.playlists["test"][0].id == "track1"
    
    def test_add_to_nonexistent_playlist(self, audio_manager, sample_tracks):
        """Test adding track to non-existent playlist creates it"""
        audio_manager.add_to_playlist("new_playlist", sample_tracks[0])
        
        assert "new_playlist" in audio_manager.playlists
        assert len(audio_manager.playlists["new_playlist"]) == 1
    
    def test_remove_from_playlist(self, audio_manager, sample_tracks):
        """Test removing track from playlist"""
        audio_manager.create_playlist("test", sample_tracks)
        
        result = audio_manager.remove_from_playlist("test", "track2")
        
        assert result is True
        assert len(audio_manager.playlists["test"]) == 2
        assert all(t.id != "track2" for t in audio_manager.playlists["test"])
    
    def test_remove_nonexistent_track(self, audio_manager, sample_tracks):
        """Test removing non-existent track"""
        audio_manager.create_playlist("test", sample_tracks)
        
        result = audio_manager.remove_from_playlist("test", "nonexistent")
        
        assert result is False
        assert len(audio_manager.playlists["test"]) == 3
    
    def test_select_playlist(self, audio_manager, sample_tracks):
        """Test selecting playlist"""
        audio_manager.create_playlist("test", sample_tracks)
        
        result = audio_manager.select_playlist("test")
        
        assert result is True
        assert audio_manager.current_playlist == "test"
        assert audio_manager.playlist_index == 0
    
    def test_select_nonexistent_playlist(self, audio_manager):
        """Test selecting non-existent playlist"""
        result = audio_manager.select_playlist("nonexistent")
        
        assert result is False
        assert audio_manager.current_playlist is None
    
    def test_get_playlists(self, audio_manager, sample_tracks):
        """Test getting all playlists"""
        audio_manager.create_playlist("playlist1", sample_tracks[:2])
        audio_manager.create_playlist("playlist2", sample_tracks[2:])
        
        playlists = audio_manager.get_playlists()
        
        assert len(playlists) == 2
        assert "playlist1" in playlists
        assert "playlist2" in playlists
        assert len(playlists["playlist1"]) == 2
        assert len(playlists["playlist2"]) == 1


class TestBGMPlayback:
    """Test BGM playback functions"""
    
    @pytest.mark.asyncio
    async def test_play_bgm_from_playlist(self, audio_manager, sample_tracks):
        """Test playing BGM from playlist"""
        audio_manager.create_playlist("test", sample_tracks)
        audio_manager.select_playlist("test")
        
        result = await audio_manager.play_bgm()
        
        assert result is True
        channel = audio_manager.channels[AudioChannel.BGM]
        assert channel.state == PlaybackState.PLAYING
        assert channel.current_track.id == "track1"
    
    @pytest.mark.asyncio
    async def test_play_specific_track(self, audio_manager, sample_tracks):
        """Test playing specific track"""
        result = await audio_manager.play_bgm(sample_tracks[1])
        
        assert result is True
        channel = audio_manager.channels[AudioChannel.BGM]
        assert channel.current_track.id == "track2"
    
    @pytest.mark.asyncio
    async def test_play_bgm_no_track(self, audio_manager):
        """Test playing BGM with no track available"""
        result = await audio_manager.play_bgm()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_pause_bgm(self, audio_manager, sample_tracks):
        """Test pausing BGM"""
        await audio_manager.play_bgm(sample_tracks[0])
        await audio_manager.pause_bgm()
        
        channel = audio_manager.channels[AudioChannel.BGM]
        assert channel.state == PlaybackState.PAUSED
    
    @pytest.mark.asyncio
    async def test_resume_bgm(self, audio_manager, sample_tracks):
        """Test resuming BGM"""
        await audio_manager.play_bgm(sample_tracks[0])
        await audio_manager.pause_bgm()
        await audio_manager.resume_bgm()
        
        channel = audio_manager.channels[AudioChannel.BGM]
        assert channel.state == PlaybackState.PLAYING
    
    @pytest.mark.asyncio
    async def test_stop_bgm(self, audio_manager, sample_tracks):
        """Test stopping BGM"""
        await audio_manager.play_bgm(sample_tracks[0])
        await audio_manager.stop_bgm()
        
        channel = audio_manager.channels[AudioChannel.BGM]
        assert channel.state == PlaybackState.STOPPED
        assert channel.position == 0.0
    
    @pytest.mark.asyncio
    async def test_next_track(self, audio_manager, sample_tracks):
        """Test skipping to next track"""
        audio_manager.create_playlist("test", sample_tracks)
        audio_manager.select_playlist("test")
        await audio_manager.play_bgm()
        
        result = await audio_manager.next_track()
        
        assert result is True
        channel = audio_manager.channels[AudioChannel.BGM]
        assert channel.current_track.id == "track2"
        assert audio_manager.playlist_index == 1
    
    @pytest.mark.asyncio
    async def test_next_track_wrap_around(self, audio_manager, sample_tracks):
        """Test next track wraps around with repeat all"""
        audio_manager.create_playlist("test", sample_tracks)
        audio_manager.select_playlist("test")
        audio_manager.playlist_index = 2  # Last track
        await audio_manager.play_bgm()
        
        result = await audio_manager.next_track()
        
        assert result is True
        assert audio_manager.playlist_index == 0
    
    @pytest.mark.asyncio
    async def test_next_track_no_repeat(self, audio_manager, sample_tracks):
        """Test next track stops at end with no repeat"""
        audio_manager.create_playlist("test", sample_tracks)
        audio_manager.select_playlist("test")
        audio_manager.repeat = RepeatMode.NONE
        audio_manager.playlist_index = 2  # Last track
        await audio_manager.play_bgm()
        
        result = await audio_manager.next_track()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_previous_track(self, audio_manager, sample_tracks):
        """Test going to previous track"""
        audio_manager.create_playlist("test", sample_tracks)
        audio_manager.select_playlist("test")
        audio_manager.playlist_index = 1
        await audio_manager.play_bgm()
        
        result = await audio_manager.previous_track()
        
        assert result is True
        channel = audio_manager.channels[AudioChannel.BGM]
        assert channel.current_track.id == "track1"


class TestSoundEffects:
    """Test sound effect functions"""
    
    def test_register_se(self, audio_manager, sample_se):
        """Test registering sound effect"""
        audio_manager.register_se(sample_se)
        
        assert "se_happy" in audio_manager.sound_effects
        assert audio_manager.sound_effects["se_happy"].trigger == "happy"
    
    @pytest.mark.asyncio
    async def test_play_se(self, audio_manager, sample_se):
        """Test playing sound effect"""
        audio_manager.register_se(sample_se)
        
        result = await audio_manager.play_se("se_happy")
        
        assert result is True
        channel = audio_manager.channels[AudioChannel.SE]
        assert channel.state == PlaybackState.PLAYING
    
    @pytest.mark.asyncio
    async def test_play_se_nonexistent(self, audio_manager):
        """Test playing non-existent sound effect"""
        result = await audio_manager.play_se("nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_play_se_cooldown(self, audio_manager, sample_se):
        """Test sound effect cooldown"""
        audio_manager.register_se(sample_se)
        
        await audio_manager.play_se("se_happy")
        result = await audio_manager.play_se("se_happy")  # Second play
        
        assert result is False  # On cooldown
    
    @pytest.mark.asyncio
    async def test_play_se_force_bypass_cooldown(self, audio_manager, sample_se):
        """Test force playing bypasses cooldown"""
        audio_manager.register_se(sample_se)
        
        await audio_manager.play_se("se_happy")
        result = await audio_manager.play_se("se_happy", force=True)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_trigger_se(self, audio_manager, sample_se):
        """Test triggering sound effect by emotion"""
        audio_manager.register_se(sample_se)
        
        result = await audio_manager.trigger_se("happy")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_trigger_se_no_match(self, audio_manager, sample_se):
        """Test triggering with no matching sound effect"""
        audio_manager.register_se(sample_se)
        
        result = await audio_manager.trigger_se("angry")
        
        assert result is False
    
    def test_get_se_by_trigger(self, audio_manager, sample_se):
        """Test getting sound effects by trigger"""
        audio_manager.register_se(sample_se)
        se2 = SoundEffect(
            id="se_happy2",
            path=Path("audio/se/happy2.wav"),
            name="Happy Sound 2",
            trigger="happy",
        )
        audio_manager.register_se(se2)
        
        results = audio_manager.get_se_by_trigger("happy")
        
        assert len(results) == 2


class TestVolumeControl:
    """Test volume control functions"""
    
    def test_set_volume(self, audio_manager):
        """Test setting volume"""
        audio_manager.set_volume(AudioChannel.BGM, 0.5)
        
        assert audio_manager.channels[AudioChannel.BGM].volume == 0.5
    
    def test_set_volume_clamp(self, audio_manager):
        """Test volume is clamped to valid range"""
        audio_manager.set_volume(AudioChannel.BGM, 1.5)
        assert audio_manager.channels[AudioChannel.BGM].volume == 1.0
        
        audio_manager.set_volume(AudioChannel.BGM, -0.5)
        assert audio_manager.channels[AudioChannel.BGM].volume == 0.0
    
    def test_get_volume(self, audio_manager):
        """Test getting volume"""
        audio_manager.set_volume(AudioChannel.SE, 0.7)
        
        volume = audio_manager.get_volume(AudioChannel.SE)
        
        assert volume == 0.7
    
    def test_mute(self, audio_manager):
        """Test muting channel"""
        audio_manager.set_muted(AudioChannel.BGM, True)
        
        assert audio_manager.is_muted(AudioChannel.BGM) is True
    
    def test_unmute(self, audio_manager):
        """Test unmuting channel"""
        audio_manager.set_muted(AudioChannel.BGM, True)
        audio_manager.set_muted(AudioChannel.BGM, False)
        
        assert audio_manager.is_muted(AudioChannel.BGM) is False


class TestDucking:
    """Test audio ducking functions"""
    
    @pytest.mark.asyncio
    async def test_start_ducking(self, audio_manager, sample_tracks):
        """Test starting ducking"""
        audio_manager.set_volume(AudioChannel.BGM, 1.0)
        await audio_manager.play_bgm(sample_tracks[0])
        
        await audio_manager.start_ducking()
        
        assert audio_manager._is_ducking is True
        assert audio_manager.channels[AudioChannel.BGM].volume < 1.0
    
    @pytest.mark.asyncio
    async def test_stop_ducking(self, audio_manager, sample_tracks):
        """Test stopping ducking"""
        audio_manager.set_volume(AudioChannel.BGM, 1.0)
        await audio_manager.play_bgm(sample_tracks[0])
        await audio_manager.start_ducking()
        
        await audio_manager.stop_ducking()
        
        assert audio_manager._is_ducking is False
        assert audio_manager.channels[AudioChannel.BGM].volume == 1.0
    
    @pytest.mark.asyncio
    async def test_ducking_disabled(self, audio_manager, sample_tracks):
        """Test ducking when disabled"""
        audio_manager.auto_duck = False
        audio_manager.set_volume(AudioChannel.BGM, 1.0)
        await audio_manager.play_bgm(sample_tracks[0])
        
        await audio_manager.start_ducking()
        
        assert audio_manager._is_ducking is False
        assert audio_manager.channels[AudioChannel.BGM].volume == 1.0


class TestState:
    """Test state management"""
    
    def test_get_state(self, audio_manager, sample_tracks):
        """Test getting full state"""
        audio_manager.create_playlist("test", sample_tracks)
        audio_manager.select_playlist("test")
        
        state = audio_manager.get_state()
        
        assert "channels" in state
        assert "current_playlist" in state
        assert "shuffle" in state
        assert "repeat" in state
        assert state["current_playlist"] == "test"
        assert state["playlists"] == ["test"]
    
    def test_track_to_dict(self, sample_tracks):
        """Test track serialization"""
        track = sample_tracks[0]
        
        data = track.to_dict()
        
        assert data["id"] == "track1"
        assert data["name"] == "Track One"
        assert data["duration"] == 180.0
    
    def test_se_to_dict(self, sample_se):
        """Test sound effect serialization"""
        data = sample_se.to_dict()
        
        assert data["id"] == "se_happy"
        assert data["trigger"] == "happy"
        assert data["cooldown"] == 0.5


class TestCallbacks:
    """Test callback registration"""
    
    @pytest.mark.asyncio
    async def test_on_track_change_callback(self, audio_manager, sample_tracks):
        """Test track change callback"""
        callback_called = []
        
        def callback(track):
            callback_called.append(track)
        
        audio_manager.on_track_change(callback)
        await audio_manager.play_bgm(sample_tracks[0])
        
        assert len(callback_called) == 1
        assert callback_called[0].id == "track1"
    
    @pytest.mark.asyncio
    async def test_on_se_play_callback(self, audio_manager, sample_se):
        """Test SE play callback"""
        callback_called = []
        
        def callback(se):
            callback_called.append(se)
        
        audio_manager.register_se(sample_se)
        audio_manager.on_se_play(callback)
        await audio_manager.play_se("se_happy")
        
        assert len(callback_called) == 1
        assert callback_called[0].id == "se_happy"
