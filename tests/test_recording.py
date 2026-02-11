"""Recording Mode Tests"""

from backend.core.emotion import Emotion
from backend.modes.recording import Script, ScriptLine


class TestScript:
    def test_from_text_simple(self):
        content = """おはロビィ！
今日もがんばるっす！"""

        script = Script.from_text(content, title="Test")
        assert script.title == "Test"
        assert len(script.lines) == 2
        assert script.lines[0].text == "おはロビィ！"

    def test_from_text_with_emotion_tags(self):
        content = """[happy] 嬉しいっす！
[sad] 悲しいっす..."""

        script = Script.from_text(content)
        assert script.lines[0].emotion == Emotion.HAPPY
        assert script.lines[0].text == "嬉しいっす！"
        assert script.lines[1].emotion == Emotion.SAD

    def test_from_text_empty_lines_ignored(self):
        content = """行1

行2

"""
        script = Script.from_text(content)
        assert len(script.lines) == 2

    def test_from_json(self):
        content = """{
    "title": "テスト台本",
    "scenes": [
        {
            "id": "scene1",
            "lines": [
                {"text": "こんにちは", "emotion": "happy"},
                {"text": "さようなら", "emotion": "sad", "wait_after": 1.0}
            ]
        }
    ]
}"""

        script = Script.from_json(content)
        assert script.title == "テスト台本"
        assert len(script.lines) == 2
        assert script.lines[0].text == "こんにちは"
        assert script.lines[0].emotion == Emotion.HAPPY
        assert script.lines[1].wait_after == 1.0


class TestScriptLine:
    def test_from_dict_basic(self):
        data = {"text": "テスト"}
        line = ScriptLine.from_dict(data)
        assert line.text == "テスト"
        assert line.emotion == Emotion.NEUTRAL

    def test_from_dict_with_emotion(self):
        data = {"text": "テスト", "emotion": "excited"}
        line = ScriptLine.from_dict(data)
        assert line.emotion == Emotion.EXCITED

    def test_from_dict_invalid_emotion(self):
        data = {"text": "テスト", "emotion": "invalid"}
        line = ScriptLine.from_dict(data)
        assert line.emotion == Emotion.NEUTRAL
