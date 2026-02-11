"""Avatar Engine Tests"""

from pathlib import Path

from backend.core.avatar import (
    AvatarFrame,
    AvatarParts,
    Expression,
    LipsyncAnalyzer,
    LipsyncConfig,
    MouthShape,
)


class TestLipsyncConfig:
    """LipsyncConfig tests"""

    def test_default_values(self):
        config = LipsyncConfig()
        assert config.fps == 30
        assert config.mouth_sensitivity == 0.5
        assert config.threshold_small == 0.1
        assert config.threshold_medium == 0.3
        assert config.threshold_large == 0.6


class TestLipsyncAnalyzer:
    """LipsyncAnalyzer tests"""

    def test_rms_to_mouth_shape_closed(self):
        analyzer = LipsyncAnalyzer()
        shape = analyzer._rms_to_mouth_shape(0.05)
        assert shape == MouthShape.CLOSED

    def test_rms_to_mouth_shape_small(self):
        analyzer = LipsyncAnalyzer()
        shape = analyzer._rms_to_mouth_shape(0.15)
        assert shape == MouthShape.OPEN_SMALL

    def test_rms_to_mouth_shape_medium(self):
        analyzer = LipsyncAnalyzer()
        shape = analyzer._rms_to_mouth_shape(0.45)
        assert shape == MouthShape.OPEN_MEDIUM

    def test_rms_to_mouth_shape_large(self):
        analyzer = LipsyncAnalyzer()
        shape = analyzer._rms_to_mouth_shape(0.8)
        assert shape == MouthShape.OPEN_LARGE

    def test_should_blink(self):
        config = LipsyncConfig(blink_interval_ms=3000, blink_duration_ms=150)
        analyzer = LipsyncAnalyzer(config)

        # まばたき中
        assert analyzer._should_blink(0) is True
        assert analyzer._should_blink(100) is True

        # まばたき終了後
        assert analyzer._should_blink(200) is False
        assert analyzer._should_blink(1000) is False

        # 次のまばたき周期
        assert analyzer._should_blink(3000) is True
        assert analyzer._should_blink(3100) is True
        assert analyzer._should_blink(3200) is False

    def test_generate_silent_frames(self):
        analyzer = LipsyncAnalyzer(LipsyncConfig(fps=30))
        frames = analyzer._generate_silent_frames(1000)

        # 30fps x 1秒 = 約30フレーム
        assert len(frames) > 25
        assert all(f.mouth_shape == MouthShape.CLOSED for f in frames)


class TestAvatarFrame:
    """AvatarFrame tests"""

    def test_creation(self):
        frame = AvatarFrame(
            timestamp_ms=100,
            mouth_shape=MouthShape.OPEN_MEDIUM,
            expression=Expression.HAPPY,
            blink=True,
        )

        assert frame.timestamp_ms == 100
        assert frame.mouth_shape == MouthShape.OPEN_MEDIUM
        assert frame.expression == Expression.HAPPY
        assert frame.blink is True


class TestAvatarParts:
    """AvatarParts tests"""

    def test_creation(self):
        parts = AvatarParts(
            base=Path("./avatar/base.png"),
            mouth_closed=Path("./avatar/mouth_closed.png"),
        )

        assert parts.base == Path("./avatar/base.png")
        assert parts.mouth_closed == Path("./avatar/mouth_closed.png")
        assert parts.mouth_open_s is None
