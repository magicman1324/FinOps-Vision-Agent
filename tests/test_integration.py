"""音频全链路集成测试 — VAD→WS→ASR→TTS 端到端"""

import base64
import json
import struct
import math

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _make_pcm(duration_sec=1.0, freq=440, sample_rate=16000):
    """生成 16kHz 16-bit mono PCM 正弦波 (Intel LE)"""
    n = int(sample_rate * duration_sec)
    samples = []
    for i in range(n):
        t = i / sample_rate
        val = int(32767 * 0.3 * math.sin(2 * math.pi * freq * t))
        samples.append(val)
    return b"".join(struct.pack("<h", s) for s in samples)


def _make_silence(duration_sec=0.5, sample_rate=16000):
    """生成静音 PCM"""
    n = int(sample_rate * duration_sec)
    return b"".join(struct.pack("<h", 0) for _ in range(n))


@pytest.fixture
def pcm_1s():
    return _make_pcm(1.0, 440)


@pytest.fixture
def silence_500ms():
    return _make_silence(0.5)


@pytest.fixture
def pcm_b64(pcm_1s):
    return base64.b64encode(pcm_1s).decode()


class TestAudioPipeline:
    """完整管线: audio→ASR→TTS 流式推送"""

    def test_full_pipeline(self, client, pcm_b64):
        from unittest.mock import patch

        with (
            patch("server.main.speech_to_text", return_value="你好世界"),
            patch(
                "server.main.text_to_speech_stream",
                return_value=_async_gen(
                    {"audio": "Y2h1bmsx", "is_final": False},
                    {"audio": "", "is_final": True},
                ),
            ),
        ):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "audio", "audio": pcm_b64})

                # 1. ASR result
                r1 = ws.receive_json()
                assert r1["type"] == "asr_result"
                assert r1["text"] == "你好世界"

                # 2. TTS chunk
                r2 = ws.receive_json()
                assert r2["audio"] == "Y2h1bmsx"
                assert r2["is_final"] is False

                # 3. TTS final
                r3 = ws.receive_json()
                assert r3["is_final"] is True

    def test_pcm_roundtrip(self, client, pcm_b64):
        """验证 Base64 PCM 从客户端编码到服务端解码兼容"""
        from unittest.mock import patch

        decoded = base64.b64decode(pcm_b64)
        # 验证是 16-bit PCM — 每样本 2 字节, 16kHz 1s = 32000 字节
        assert len(decoded) == 32000
        assert len(decoded) % 2 == 0

        with (
            patch("server.main.speech_to_text", return_value="测试"),
            patch(
                "server.main.text_to_speech_stream",
                return_value=_async_gen({"audio": "", "is_final": True}),
            ),
        ):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "audio", "audio": pcm_b64})
                r = ws.receive_json()
                assert r["type"] == "asr_result"
                assert r["text"] == "测试"

    def test_consecutive_utterances(self, client, pcm_b64):
        """连续两句话分别识别"""
        from unittest.mock import patch

        texts = ["第一句", "第二句"]

        with (
            patch("server.main.speech_to_text", side_effect=texts),
            patch(
                "server.main.text_to_speech_stream",
                side_effect=[
                    _async_gen({"audio": "", "is_final": True}),
                    _async_gen({"audio": "", "is_final": True}),
                ],
            ),
        ):
            with client.websocket_connect("/ws") as ws:
                for expected in texts:
                    ws.send_json({"type": "audio", "audio": pcm_b64})
                    r = ws.receive_json()
                    assert r["type"] == "asr_result"
                    assert r["text"] == expected
                    # drain TTS final
                    ws.receive_json()

    def test_rapid_consecutive_sends(self, client, pcm_b64):
        """快速连续发送，验证不丢帧不乱序"""
        from unittest.mock import patch

        with (
            patch("server.main.speech_to_text", return_value="ok"),
            patch(
                "server.main.text_to_speech_stream",
                side_effect=[
                    _async_gen({"audio": "", "is_final": True})
                    for _ in range(5)
                ],
            ),
        ):
            with client.websocket_connect("/ws") as ws:
                for _ in range(5):
                    ws.send_json({"type": "audio", "audio": pcm_b64})
                # 每条消息应有 asr_result + tts final
                for i in range(5):
                    r1 = ws.receive_json()
                    assert r1["type"] == "asr_result", f"msg {i}: expected asr_result, got {r1['type']}"
                    r2 = ws.receive_json()
                    assert r2["is_final"] is True, f"msg {i}: expected final"

    def test_large_audio(self, client):
        """大音频片段 (3s)"""
        pcm = _make_pcm(3.0, 440)
        b64 = base64.b64encode(pcm).decode()

        from unittest.mock import patch

        with (
            patch("server.main.speech_to_text", return_value="长句测试"),
            patch(
                "server.main.text_to_speech_stream",
                return_value=_async_gen({"audio": "", "is_final": True}),
            ),
        ):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "audio", "audio": b64})
                r = ws.receive_json()
                assert r["type"] == "asr_result"


class TestErrorHandling:
    """错误降级路径"""

    def test_asr_error_graceful(self, client, pcm_b64):
        from unittest.mock import patch
        from server.asr import ASRError

        with patch("server.main.speech_to_text", side_effect=ASRError("fail")):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "audio", "audio": pcm_b64})
                r = ws.receive_json()
                assert r["type"] == "error"
                assert "没听清" in r["message"]

    def test_tts_error_after_asr(self, client, pcm_b64):
        from unittest.mock import patch
        from server.tts import TTSError

        with (
            patch("server.main.speech_to_text", return_value="正常"),
            patch(
                "server.main.text_to_speech_stream",
                side_effect=TTSError("tts fail"),
            ),
        ):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "audio", "audio": pcm_b64})
                # ASR should succeed
                r1 = ws.receive_json()
                assert r1["type"] == "asr_result"
                # TTS should error
                r2 = ws.receive_json()
                assert r2["type"] == "error"
                assert "语音合成" in r2["message"]


class TestEdgeCases:
    """边界场景"""

    def test_silence_audio(self, client, silence_500ms):
        """静音片段 — ASR 可能返回空，触发未识别"""
        b64 = base64.b64encode(silence_500ms).decode()

        from unittest.mock import patch

        with patch("server.main.speech_to_text", return_value="   "):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "audio", "audio": b64})
                r = ws.receive_json()
                assert r["type"] == "error"
                assert "未识别" in r["message"]

    def test_empty_base64(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "audio", "audio": ""})
            r = ws.receive_json()
            assert r["type"] == "error"
            assert "missing audio" in r["message"]

    def test_missing_audio_field(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "audio"})
            r = ws.receive_json()
            assert r["type"] == "error"

    def test_echo_still_works(self, client):
        """非 audio 消息走 echo"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "ping", "data": 42})
            r = ws.receive_json()
            assert r["type"] == "echo"
            assert r["data"]["data"] == 42


class TestVisualPipeline:
    """视觉消息协议: image→VLM→vlm_result"""

    def test_image_to_vlm_result(self, client):
        """完整视觉管线: image→VLM→vlm_result"""
        fake_jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100).decode()

        from unittest.mock import patch

        with patch("server.main.image_to_text", return_value="画面中有一张桌子"):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "image", "image": fake_jpeg})
                r = ws.receive_json()
                assert r["type"] == "vlm_result"
                assert "桌子" in r["text"]

    def test_image_missing_field(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "image"})
            r = ws.receive_json()
            assert r["type"] == "error"
            assert "missing image" in r["message"]

    def test_image_vlm_error(self, client):
        fake_jpeg = base64.b64encode(b"fake").decode()

        from unittest.mock import patch
        from server.vlm import VLMError

        with patch("server.main.image_to_text", side_effect=VLMError("fail")):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "image", "image": fake_jpeg})
                r = ws.receive_json()
                assert r["type"] == "error"
                assert "图片分析失败" in r["message"]

    def test_image_empty_result(self, client):
        fake_jpeg = base64.b64encode(b"fake").decode()

        from unittest.mock import patch

        with patch("server.main.image_to_text", return_value="   "):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "image", "image": fake_jpeg})
                r = ws.receive_json()
                assert r["type"] == "error"
                assert "未识别到画面" in r["message"]


def _async_gen(*items):
    """Helper: 创建异步生成器"""
    async def gen():
        for item in items:
            yield item
    return gen()
