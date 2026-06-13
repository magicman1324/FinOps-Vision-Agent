"""CosyVoice 流式 TTS — 文本转语音"""

import asyncio
import base64
import logging
import os
import time

import dashscope
from dashscope.audio.tts_v2 import AudioFormat, ResultCallback, SpeechSynthesizer

from server.config import DASHSCOPE_API_KEY, DASHSCOPE_TTS_MODEL, TTS_TIMEOUT

logger = logging.getLogger(__name__)
dashscope.api_key = DASHSCOPE_API_KEY

# 清除系统代理 — dashscope 内部用 aiohttp，会读 HTTP_PROXY
for _key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_key, None)


class TTSError(Exception):
    """TTS 调用失败"""


class _QueueCallback(ResultCallback):
    """将 TTS 回调数据写入 asyncio.Queue"""

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._start = time.monotonic()
        self._first = True

    def on_data(self, data: bytes) -> None:
        if self._first:
            logger.info("TTS first chunk: ttfb=%.3fs", time.monotonic() - self._start)
            self._first = False
        self._queue.put_nowait(("data", data))

    def on_complete(self) -> None:
        self._queue.put_nowait(("done", None))
        logger.info(
            "TTS done: elapsed=%.2fs", time.monotonic() - self._start
        )

    def on_error(self, message) -> None:
        self._queue.put_nowait(("error", message))


async def text_to_speech_stream(text: str):
    """
    流式文本转语音，逐个 yield Base64 编码的 MP3 chunk

    Args:
        text: 要合成的文本

    Yields:
        dict: {"audio": "<base64_mp3_chunk>", "is_final": bool}
    """
    queue: asyncio.Queue = asyncio.Queue()
    callback = _QueueCallback(queue)
    synthesizer = SpeechSynthesizer(
        model=DASHSCOPE_TTS_MODEL,
        voice="longxiaochun",
        format=AudioFormat.MP3_16000HZ_MONO_128KBPS,
        callback=callback,
    )
    try:
        synthesizer.streaming_call(text)
        synthesizer.streaming_complete()

        while True:
            msg_type, payload = await asyncio.wait_for(
                queue.get(), timeout=TTS_TIMEOUT
            )
            if msg_type == "error":
                raise TTSError(f"TTS synthesis failed: {payload}")
            if msg_type == "done":
                yield {"audio": "", "is_final": True}
                return
            if msg_type == "data":
                audio_b64 = base64.b64encode(payload).decode()
                yield {"audio": audio_b64, "is_final": False}
    except asyncio.TimeoutError:
        raise TTSError(f"TTS timeout after {TTS_TIMEOUT}s")
    except Exception:
        raise
