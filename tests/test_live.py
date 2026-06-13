"""真实 API 集成测试 — 需要 DASHSCOPE_API_KEY + DEEPSEEK_API_KEY"""

import base64
import os
import subprocess
import tempfile

import pytest


def _has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _needs_dashscope():
    return not os.getenv("DASHSCOPE_API_KEY")


def _needs_deepseek():
    return not os.getenv("DEEPSEEK_API_KEY")


# ---- TTS ----

@pytest.mark.skipif(_needs_dashscope(), reason="DASHSCOPE_API_KEY not set")
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


# ---- ASR ----

@pytest.mark.skipif(_needs_dashscope(), reason="DASHSCOPE_API_KEY not set")
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
        # 注意: 测试用纯正弦波不是语音，ASR 返回空字符串是正常行为
        # 本测试只验证 API 调用不抛异常
    finally:
        os.unlink(pcm_path)


# ---- VLM ----

@pytest.mark.skipif(_needs_dashscope(), reason="DASHSCOPE_API_KEY not set")
def test_vlm_live():
    """VLM 真实调用：生成测试图片→视觉推理→验证返回文本"""
    if not _has_module("server.vlm"):
        pytest.skip("server.vlm module not available")
    import asyncio

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img_path = tmp.name

    try:
        # 用 ffmpeg 生成 512x512 红色纯色 PNG
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=red:size=512x512:d=0.1",
                "-frames:v", "1",
                img_path,
            ],
            capture_output=True,
            check=True,
        )

        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        from server.vlm import image_to_text

        result = asyncio.run(image_to_text(img_b64, "请描述这张图片的颜色"))
        assert isinstance(result, str), "VLM 未返回文本"
        assert len(result.strip()) > 0, "VLM 返回空文本"
    finally:
        os.unlink(img_path)


# ---- LLM ----

@pytest.mark.skipif(_needs_deepseek(), reason="DEEPSEEK_API_KEY not set")
def test_llm_live():
    """LLM 真实调用：DeepSeek-V3 文本推理→验证返回文本"""
    if not _has_module("server.llm"):
        pytest.skip("server.llm module not available")
    from server.llm import ask_llm
    import asyncio

    async def run():
        return await ask_llm("用一句话回答：中国的首都是哪里？")

    result = asyncio.run(run())
    assert isinstance(result, str), "LLM 未返回文本"
    assert len(result.strip()) > 0, "LLM 返回空文本"


# ---- 端到端: LLM 降级链 ----

@pytest.mark.skipif(_needs_deepseek(), reason="DEEPSEEK_API_KEY not set")
def test_cascade_text_live():
    """LLM 文本降级链真实调用：_cascade_text L1 路径"""
    if not _has_module("server.llm"):
        pytest.skip("server.llm module not available")
    from server.main import _cascade_text
    from server.memory import ConversationMemory
    import asyncio

    async def run():
        mem = ConversationMemory()
        return await _cascade_text("今天天气怎么样", mem)

    result = asyncio.run(run())
    assert isinstance(result, str), "降级链未返回文本"
    assert len(result.strip()) > 0, "降级链返回空文本"


# ---- ASR + TTS 端到端语音链路 ----

@pytest.mark.skipif(_needs_dashscope(), reason="DASHSCOPE_API_KEY not set")
def test_speech_pipeline_live():
    """语音全链路真实调用：ASR 识别 → TTS 合成"""
    if not _has_module("server.asr") or not _has_module("server.tts"):
        pytest.skip("ASR/TTS module not available")
    from server.asr import speech_to_text
    from server.tts import text_to_speech_stream
    import asyncio

    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
        pcm_path = tmp.name

    try:
        # 生成语音 "测试" — 1kHz 正弦波 1.5 秒
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=frequency=440:duration=1.5",
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                pcm_path,
            ],
            capture_output=True,
            check=True,
        )

        with open(pcm_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        # 1. ASR
        text = speech_to_text(audio_b64)
        assert isinstance(text, str), "ASR 未返回文本"

        # 2. TTS — 对 ASR 结果（或兜底文本）做语音合成
        tts_input = text.strip() if text.strip() else "你好"
        async def run():
            chunks = []
            async for chunk in text_to_speech_stream(tts_input):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(run())
        audio_chunks = [c for c in chunks if c.get("audio")]
        assert len(audio_chunks) >= 1, "TTS 未返回音频"
        assert chunks[-1]["is_final"] is True, "TTS 未标记完成"
    finally:
        os.unlink(pcm_path)
