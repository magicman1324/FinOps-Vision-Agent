"""测试 ASR 模块"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from server.asr import ASRError, speech_to_text


class TestSpeechToText:
    def test_decodes_and_extracts_text_from_result(self):
        audio_b64 = base64.b64encode(b"fake_pcm_audio").decode()
        with patch("server.asr.Recognition") as MockRec:
            mock_result = MagicMock()
            mock_result.status_code = 200
            mock_result.output = {"sentence": [{"text": "你好世界"}]}
            MockRec.return_value.call.return_value = mock_result
            result = speech_to_text(audio_b64)
            assert result == "你好世界"
            MockRec.return_value.call.assert_called_once()

    def test_handles_dict_sentence(self):
        audio_b64 = base64.b64encode(b"fake").decode()
        with patch("server.asr.Recognition") as MockRec:
            mock_result = MagicMock()
            mock_result.status_code = 200
            mock_result.output = {"sentence": {"text": "单句"}}
            MockRec.return_value.call.return_value = mock_result
            result = speech_to_text(audio_b64)
            assert result == "单句"

    def test_returns_empty_on_missing_text(self):
        audio_b64 = base64.b64encode(b"silence").decode()
        with patch("server.asr.Recognition") as MockRec:
            mock_result = MagicMock()
            mock_result.status_code = 200
            mock_result.output = {"sentence": [{"text": ""}]}
            MockRec.return_value.call.return_value = mock_result
            result = speech_to_text(audio_b64)
            assert result == ""

    def test_raises_on_non_200(self):
        audio_b64 = base64.b64encode(b"bad").decode()
        with patch("server.asr.Recognition") as MockRec:
            mock_result = MagicMock()
            mock_result.status_code = 401
            mock_result.code = "InvalidApiKey"
            mock_result.message = "api-key is invalid"
            MockRec.return_value.call.return_value = mock_result
            with pytest.raises(ASRError, match="InvalidApiKey"):
                speech_to_text(audio_b64)

    def test_raises_on_call_exception(self):
        audio_b64 = base64.b64encode(b"bad_audio").decode()
        with patch("server.asr.Recognition") as MockRec:
            MockRec.return_value.call.side_effect = RuntimeError("network error")
            with pytest.raises(RuntimeError):
                speech_to_text(audio_b64)
