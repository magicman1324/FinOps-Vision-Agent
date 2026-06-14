"""DashScope 通义听悟 ASR — 语音转文本"""

import asyncio
import base64
import logging
import os
import sys
import tempfile
import time
import wave

import dashscope
from dashscope.audio.asr import Recognition, RecognitionResult

from server.config import DASHSCOPE_API_KEY, DASHSCOPE_ASR_MODEL, ASR_TIMEOUT

logger = logging.getLogger(__name__)
dashscope.api_key = DASHSCOPE_API_KEY

# config.py 已处理代理清除和事件循环策略，此处不重复

_debug_audio_dir = os.path.join(tempfile.gettempdir(), "xengineer3_debug")
_debug_save_count = 0


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
    global _debug_save_count
    audio_bytes = base64.b64decode(audio_base64)
    duration = len(audio_bytes) / 32000  # 16kHz 16bit mono = 32000 bytes/s
    logger.info("ASR audio: %d bytes (%.1fs)", len(audio_bytes), duration)

    if _debug_save_count < 10:
        _debug_save_count += 1
        os.makedirs(_debug_audio_dir, exist_ok=True)
        ts = int(time.time() * 1000)
        wav_path = os.path.join(_debug_audio_dir, f"asr_{ts}_{len(audio_bytes)}.wav")
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)
            wf.writeframes(audio_bytes)
        logger.info("ASR debug: saved %s", wav_path)

    recognition = Recognition(
        model=DASHSCOPE_ASR_MODEL,
        format="pcm",
        sample_rate=16000,
        callback=None,
    )
    start = time.monotonic()
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        result = recognition.call(tmp_path)
    finally:
        os.unlink(tmp_path)
    elapsed = time.monotonic() - start

    if result.status_code != 200:
        logger.error("ASR API error: code=%s message=%s", result.code, result.message)
        raise ASRError(f"ASR failed: {result.code} - {result.message}")

    text = ""
    output = result.output if isinstance(result.output, dict) else {}
    sentences = output.get("sentence", [])
    if isinstance(sentences, dict):
        sentences = [sentences]
    for s in sentences:
        if isinstance(s, dict) and s.get("text"):
            text += s["text"]

    logger.info("ASR done: text=%r, elapsed=%.2fs", text, elapsed)
    return text
