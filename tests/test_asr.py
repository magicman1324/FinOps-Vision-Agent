"""测试 ASR 模块"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from server.asr import ASRError, _TextCollector, speech_to_text


class TestTextCollector:
    def test_collects_sentence_text(self):
        collector = _TextCollector()
        mock_result = MagicMock()
        mock_sentence = MagicMock()
        mock_sentence.text = "你好世界"
        mock_result.get_sentence.return_value = mock_sentence
        collector.on_event(mock_result)
        assert collector.text == "你好世界"

    def test_accumulates_multiple_sentences(self):
        collector = _TextCollector()
        for text in ["今天", "天气", "很好"]:
            mock_result = MagicMock()
            mock_sentence = MagicMock()
            mock_sentence.text = text
            mock_result.get_sentence.return_value = mock_sentence
            collector.on_event(mock_result)
        assert collector.text == "今天天气很好"


class TestSpeechToText:
    def test_decodes_and_returns_text(self):
        audio_b64 = base64.b64encode(b"fake_pcm_audio").decode()
        with (
            patch("server.asr.Recognition") as MockRec,
            patch("server.asr._TextCollector") as MockTC,
        ):
            MockTC.return_value.text = "测试文本"
            result = speech_to_text(audio_b64)
            assert "测试文本" in result
            MockRec.return_value.call.assert_called_once()

    def test_raises_on_error(self):
        audio_b64 = base64.b64encode(b"bad_audio").decode()
        with (
            patch("server.asr.Recognition") as MockRec,
            patch("server.asr._TextCollector") as MockTC,
        ):
            MockRec.return_value.call.side_effect = ASRError(
                "service unavailable"
            )
            with pytest.raises(ASRError):
                speech_to_text(audio_b64)
