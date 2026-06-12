"""DashScope 通义听悟 ASR — 语音转文本"""

import base64
import logging
import time

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

from server.config import DASHSCOPE_API_KEY, DASHSCOPE_ASR_MODEL, ASR_TIMEOUT

logger = logging.getLogger(__name__)
dashscope.api_key = DASHSCOPE_API_KEY


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
    collector = _TextCollector()
    recognition = Recognition(
        model=DASHSCOPE_ASR_MODEL,
        format="pcm",
        sample_rate=16000,
        callback=collector,
    )
    start = time.monotonic()
    recognition.call(audio_bytes)
    elapsed = time.monotonic() - start
    logger.info("ASR done: text=%r, elapsed=%.2fs", collector.text, elapsed)
    return collector.text
