"""真实 API 集成测试 — 需要 GitHub Secrets: DASHSCOPE_API_KEY"""

import base64
import os
import subprocess
import tempfile

import pytest

_missing_key = not os.getenv("DASHSCOPE_API_KEY")


def _has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


# 模块不存在或 API Key 未配则跳过
pytestmark = pytest.mark.skipif(
    not os.getenv("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY not set in secrets",
)


def test_tts_live():
    """TTS 真实调用：文本→流式合成→验证输出"""
    if not _has_module("server.tts"):
        pytest.skip("server.tts module not available")
    from server.tts import text_to_speech_stream
    import asyncio

    async def run():
        chunks = []
        async for chunk in text_to_speech_stream("你好世界"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())
    audio_chunks = [c for c in chunks if c.get("audio")]
    assert len(audio_chunks) >= 1, "TTS 未返回音频数据"
    assert chunks[-1]["is_final"] is True, "TTS 未标记完成"


def test_asr_live():
    """ASR 真实调用：生成测试音频→识别→验证不抛异常"""
    if not _has_module("server.asr"):
        pytest.skip("server.asr module not available")

    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
        pcm_path = tmp.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=frequency=1000:duration=2",
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                pcm_path,
            ],
            capture_output=True,
            check=True,
        )

        with open(pcm_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        from server.asr import speech_to_text

        result = speech_to_text(audio_b64)
        assert isinstance(result, str), "ASR 未返回文本"
    finally:
        os.unlink(pcm_path)
