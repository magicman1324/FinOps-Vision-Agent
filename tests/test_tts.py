"""测试 TTS 模块"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from server.tts import TTSError, _QueueCallback, text_to_speech_stream


class TestQueueCallback:
    def test_on_data_puts_to_queue(self):
        q = MagicMock()
        cb = _QueueCallback(q)
        cb.on_data(b"hello")
        q.put_nowait.assert_called_once_with(("data", b"hello"))

    def test_on_complete_puts_done(self):
        q = MagicMock()
        cb = _QueueCallback(q)
        cb.on_complete()
        q.put_nowait.assert_called_once_with(("done", None))

    def test_on_error_puts_error(self):
        q = MagicMock()
        cb = _QueueCallback(q)
        cb.on_error("fail")
        q.put_nowait.assert_called_once_with(("error", "fail"))


class TestTextToSpeechStream:
    @pytest.mark.asyncio
    async def test_yields_data_then_done(self):
        with patch("server.tts.SpeechSynthesizer"):
            queue = asyncio.Queue()
            queue.put_nowait(("data", b"mp3_chunk"))
            queue.put_nowait(("done", None))
            with patch("server.tts.asyncio.Queue", return_value=queue):
                chunks = []
                async for chunk in text_to_speech_stream("你好"):
                    chunks.append(chunk)

                assert len(chunks) == 2
                assert chunks[0]["audio"] != ""
                assert chunks[0]["is_final"] is False
                assert chunks[1]["is_final"] is True

    @pytest.mark.asyncio
    async def test_raises_on_error(self):
        with patch("server.tts.SpeechSynthesizer"):
            queue = asyncio.Queue()
            queue.put_nowait(("error", "network error"))
            with patch("server.tts.asyncio.Queue", return_value=queue):
                with pytest.raises(TTSError):
                    async for _ in text_to_speech_stream("test"):
                        pass
