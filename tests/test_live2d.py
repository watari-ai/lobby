"""Tests for Live2D module"""


from backend.core.emotion import Emotion
from backend.core.live2d import (
    EmotionDrivenConfig,
    EmotionDrivenLive2D,
    Live2DConfig,
    Live2DExpression,
    Live2DFrame,
    Live2DLipsyncAnalyzer,
    Live2DParameters,
    emotion_to_live2d_expression,
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


class TestEmotionToLive2DExpression:
    """emotion_to_live2d_expression tests"""

    def test_happy_mapping(self):
        """HAPPYが正しく変換される"""
        result = emotion_to_live2d_expression(Emotion.HAPPY)
        assert result == Live2DExpression.HAPPY

    def test_sad_mapping(self):
        """SADが正しく変換される"""
        result = emotion_to_live2d_expression(Emotion.SAD)
        assert result == Live2DExpression.SAD

    def test_excited_mapping(self):
        """EXCITEDが正しく変換される"""
        result = emotion_to_live2d_expression(Emotion.EXCITED)
        assert result == Live2DExpression.EXCITED

    def test_angry_mapping(self):
        """ANGRYが正しく変換される"""
        result = emotion_to_live2d_expression(Emotion.ANGRY)
        assert result == Live2DExpression.ANGRY

    def test_surprised_mapping(self):
        """SURPRISEDが正しく変換される"""
        result = emotion_to_live2d_expression(Emotion.SURPRISED)
        assert result == Live2DExpression.SURPRISED

    def test_neutral_mapping(self):
        """NEUTRALが正しく変換される"""
        result = emotion_to_live2d_expression(Emotion.NEUTRAL)
        assert result == Live2DExpression.NEUTRAL

    def test_all_emotions_mapped(self):
        """すべてのEmotionがマッピングされている"""
        for emotion in Emotion:
            result = emotion_to_live2d_expression(emotion)
            assert isinstance(result, Live2DExpression)


class TestEmotionDrivenConfig:
    """EmotionDrivenConfig tests"""

    def test_default_values(self):
        """デフォルト値が正しく設定されている"""
        config = EmotionDrivenConfig()

        assert config.intensity_multiplier == 1.5
        assert config.neutral_threshold == 0.3
        assert config.transition_frames == 10

    def test_custom_values(self):
        """カスタム値が設定できる"""
        config = EmotionDrivenConfig(
            intensity_multiplier=2.0,
            neutral_threshold=0.5,
        )

        assert config.intensity_multiplier == 2.0
        assert config.neutral_threshold == 0.5


class TestEmotionDrivenLive2D:
    """EmotionDrivenLive2D tests"""

    def test_initialization(self):
        """初期化が正常に動作する"""
        engine = EmotionDrivenLive2D()

        assert engine.emotion_analyzer is not None
        assert engine.lipsync_analyzer is not None
        assert engine._current_expression == Live2DExpression.NEUTRAL

    def test_analyze_text_happy(self):
        """嬉しいテキストの分析"""
        engine = EmotionDrivenLive2D()

        expression, intensity = engine.analyze_text("やったー！嬉しい！")

        assert expression == Live2DExpression.HAPPY
        assert intensity > 0.3

    def test_analyze_text_excited(self):
        """興奮したテキストの分析"""
        engine = EmotionDrivenLive2D()

        expression, intensity = engine.analyze_text("マジすごいっす！やばいっすね！！")

        assert expression == Live2DExpression.EXCITED
        assert intensity > 0.5

    def test_analyze_text_sad(self):
        """悲しいテキストの分析"""
        engine = EmotionDrivenLive2D()

        expression, intensity = engine.analyze_text("悲しい...辛いな...")

        assert expression == Live2DExpression.SAD
        assert intensity > 0.3

    def test_analyze_text_neutral_fallback(self):
        """低強度はneutralにフォールバック"""
        config = EmotionDrivenConfig(neutral_threshold=0.9)
        engine = EmotionDrivenLive2D(emotion_config=config)

        expression, intensity = engine.analyze_text("こんにちは")

        assert expression == Live2DExpression.NEUTRAL

    def test_get_expression_params(self):
        """表情パラメータの取得"""
        engine = EmotionDrivenLive2D()

        expression, params = engine.get_expression_params("嬉しいっす！")

        assert expression == Live2DExpression.HAPPY
        assert isinstance(params, Live2DParameters)
        assert params.param_mouth_form > 0  # 笑顔

    def test_apply_intensity(self):
        """強度の適用"""
        engine = EmotionDrivenLive2D()

        frames = [
            Live2DFrame(
                timestamp_ms=0,
                parameters=Live2DParameters(
                    param_mouth_form=0.5,
                    param_brow_l_y=0.3,
                    param_brow_r_y=0.3,
                ),
            )
        ]

        # 高強度を適用
        engine._apply_intensity(frames, 0.9)

        # パラメータが増幅されている
        assert frames[0].parameters.param_mouth_form > 0.5
        assert frames[0].parameters.param_brow_l_y > 0.3

    def test_apply_intensity_clipping(self):
        """強度適用時の範囲クリップ"""
        engine = EmotionDrivenLive2D()

        frames = [
            Live2DFrame(
                timestamp_ms=0,
                parameters=Live2DParameters(
                    param_mouth_form=0.9,
                    param_brow_l_y=0.9,
                    param_brow_r_y=0.9,
                ),
            )
        ]

        # 非常に高い強度を適用
        engine._apply_intensity(frames, 1.0)

        # 範囲内にクリップされている
        assert -1.0 <= frames[0].parameters.param_mouth_form <= 1.0
        assert -1.0 <= frames[0].parameters.param_brow_l_y <= 1.0
        assert -1.0 <= frames[0].parameters.param_brow_r_y <= 1.0
