"""DashScope 通义听悟 ASR — 语音转文本"""

import asyncio
import base64
import logging
import os
import sys
import tempfile
import time

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

from server.config import DASHSCOPE_API_KEY, DASHSCOPE_ASR_MODEL, ASR_TIMEOUT

logger = logging.getLogger(__name__)
dashscope.api_key = DASHSCOPE_API_KEY

# 清除系统代理 — dashscope 内部用 aiohttp，会读 HTTP_PROXY
for _key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_key, None)

# Windows: ProactorEventLoop SSL 有 bug，切 Selector
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class _TextCollector(RecognitionCallback):
    """收集 ASR 识别结果"""

    def __init__(self):
        self.text = ""

    def on_event(self, result: RecognitionResult) -> None:
        sentence = result.get_sentence()
        if sentence and sentence.text:
            self.text += sentence.text

    def on_error(self, result: RecognitionResult) -> None:
        logger.error("ASR error: %s", result)
        raise ASRError(f"ASR recognition failed: {result}")


class ASRError(Exception):
    """ASR 调用失败"""


def speech_to_text(audio_base64: str) -> str:
    """
    将 Base64 编码的 PCM 音频转为文本

    Args:
        audio_base64: Base64 编码的 PCM 音频（16kHz, 16bit, mono）

    Returns:
        识别出的文本
    """
    audio_bytes = base64.b64decode(audio_base64)
    duration = len(audio_bytes) / 32000  # 16kHz 16bit mono = 32000 bytes/s
    logger.info("ASR audio: %d bytes (%.1fs)", len(audio_bytes), duration)

    collector = _TextCollector()
    recognition = Recognition(
        model=DASHSCOPE_ASR_MODEL,
        format="pcm",
        sample_rate=16000,
        callback=collector,
    )
    start = time.monotonic()
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        recognition.call(tmp_path)
    finally:
        os.unlink(tmp_path)
    elapsed = time.monotonic() - start
    logger.info("ASR done: text=%r, elapsed=%.2fs", collector.text, elapsed)
    return collector.text
