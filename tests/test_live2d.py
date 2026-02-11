"""Tests for Live2D module"""

import pytest

from backend.core.live2d import (
    Live2DConfig,
    Live2DExpression,
    Live2DFrame,
    Live2DLipsyncAnalyzer,
    Live2DParameters,
)


class TestLive2DParameters:
    """Live2DParameters tests"""

    def test_default_values(self):
        """デフォルト値が正しく設定されている"""
        params = Live2DParameters()

        assert params.param_mouth_open_y == 0.0
        assert params.param_eye_l_open == 1.0
        assert params.param_eye_r_open == 1.0
        assert params.param_breath == 0.0

    def test_to_dict(self):
        """辞書変換が正しく動作する"""
        params = Live2DParameters(
            param_mouth_open_y=0.5,
            param_mouth_form=0.3,
        )

        d = params.to_dict()

        assert d["ParamMouthOpenY"] == 0.5
        assert d["ParamMouthForm"] == 0.3
        assert "ParamEyeLOpen" in d
        assert "ParamBreath" in d

    def test_to_dict_contains_all_params(self):
        """すべてのパラメータが辞書に含まれる"""
        params = Live2DParameters()
        d = params.to_dict()

        expected_keys = [
            "ParamMouthOpenY",
            "ParamMouthForm",
            "ParamEyeLOpen",
            "ParamEyeROpen",
            "ParamEyeBallX",
            "ParamEyeBallY",
            "ParamBrowLY",
            "ParamBrowRY",
            "ParamAngleX",
            "ParamAngleY",
            "ParamAngleZ",
            "ParamBodyAngleX",
            "ParamBodyAngleY",
            "ParamBodyAngleZ",
            "ParamBreath",
        ]

        for key in expected_keys:
            assert key in d, f"Missing key: {key}"


class TestLive2DConfig:
    """Live2DConfig tests"""

    def test_default_expression_presets(self):
        """表情プリセットが正しく設定されている"""
        config = Live2DConfig()

        assert Live2DExpression.NEUTRAL in config.expression_presets
        assert Live2DExpression.HAPPY in config.expression_presets
        assert Live2DExpression.SAD in config.expression_presets
        assert Live2DExpression.EXCITED in config.expression_presets
        assert Live2DExpression.SURPRISED in config.expression_presets
        assert Live2DExpression.ANGRY in config.expression_presets

    def test_happy_preset(self):
        """Happy表情のプリセットが正しい"""
        config = Live2DConfig()
        happy = config.expression_presets[Live2DExpression.HAPPY]

        assert happy["param_mouth_form"] > 0  # 笑顔


class TestLive2DLipsyncAnalyzer:
    """Live2DLipsyncAnalyzer tests"""

    def test_initialization(self):
        """初期化が正常に動作する"""
        analyzer = Live2DLipsyncAnalyzer()
        assert analyzer.config.fps == 30

    def test_custom_config(self):
        """カスタム設定が反映される"""
        config = Live2DConfig(fps=60, mouth_sensitivity=0.8)
        analyzer = Live2DLipsyncAnalyzer(config)

        assert analyzer.config.fps == 60
        assert analyzer.config.mouth_sensitivity == 0.8

    def test_generate_idle_frames(self):
        """アイドルフレームが正しく生成される"""
        analyzer = Live2DLipsyncAnalyzer()
        frames = analyzer._generate_idle_frames(1000, Live2DExpression.NEUTRAL)

        assert len(frames) > 0
        assert all(isinstance(f, Live2DFrame) for f in frames)
        assert all(f.parameters.param_mouth_open_y == 0.0 for f in frames)

    def test_calculate_blink(self):
        """まばたきが正しく計算される"""
        analyzer = Live2DLipsyncAnalyzer()

        # まばたき中
        blink_value = analyzer._calculate_blink(50)  # blink_duration_ms内
        assert blink_value > 0

        # まばたき終了後
        blink_value = analyzer._calculate_blink(500)
        assert blink_value == 0.0

    def test_calculate_breath(self):
        """呼吸が正しく計算される"""
        analyzer = Live2DLipsyncAnalyzer()

        # 呼吸値は0-1の範囲
        for t in range(0, 4000, 100):
            breath = analyzer._calculate_breath(t)
            assert 0.0 <= breath <= 1.0

    def test_expression_affects_parameters(self):
        """表情がパラメータに影響する"""
        analyzer = Live2DLipsyncAnalyzer()

        neutral_params = analyzer._generate_parameters(0, 0.0, Live2DExpression.NEUTRAL)
        happy_params = analyzer._generate_parameters(0, 0.0, Live2DExpression.HAPPY)

        # Happy表情はmouthFormが正
        assert happy_params.param_mouth_form > neutral_params.param_mouth_form


class TestLive2DFrame:
    """Live2DFrame tests"""

    def test_default_frame(self):
        """デフォルトフレームが正しく作成される"""
        frame = Live2DFrame(timestamp_ms=0)

        assert frame.timestamp_ms == 0
        assert isinstance(frame.parameters, Live2DParameters)
        assert frame.expression == Live2DExpression.NEUTRAL
        assert frame.motion is None

    def test_frame_with_expression(self):
        """表情付きフレームが正しく作成される"""
        frame = Live2DFrame(
            timestamp_ms=100,
            expression=Live2DExpression.HAPPY,
            motion="greeting",
        )

        assert frame.expression == Live2DExpression.HAPPY
        assert frame.motion == "greeting"
