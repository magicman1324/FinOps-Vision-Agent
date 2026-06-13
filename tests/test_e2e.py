"""端到端联调测试 — 模拟浏览器完整交互流程"""

import base64
import struct
import math

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _make_pcm(duration_sec=1.0):
    """生成 16kHz 16-bit mono PCM 440Hz 正弦波"""
    n = int(16000 * duration_sec)
    samples = [int(32767 * 0.3 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(n)]
    return b"".join(struct.pack("<h", s) for s in samples)


class TestE2EUserFlow:
    """模拟真实用户交互流程"""

    def test_full_dual_channel_flow(self, client):
        """用户说话+画面: 音频走ASR→TTS, 图片走VLM"""
        from unittest.mock import patch

        pcm = _make_pcm(1.5)
        audio_b64 = base64.b64encode(pcm).decode()
        fake_jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100).decode()

        with client.websocket_connect("/ws") as ws:
            # 音频通道
            with (
                patch("server.main.speech_to_text", return_value="用户说了什么"),
                patch(
                    "server.main.text_to_speech_stream",
                    return_value=_async_gen(
                        {"type": "audio", "audio": "bW9ja2F1ZGlv", "is_final": False},
                        {"type": "audio", "audio": "", "is_final": True},
                    ),
                ),
            ):
                ws.send_json({"type": "audio", "audio": audio_b64})
                r = ws.receive_json()
                assert r["type"] == "asr_result"
                ws.receive_json()  # text_result
                r = ws.receive_json()
                assert r["is_final"] is False
                r = ws.receive_json()
                assert r["is_final"] is True

            # 视觉通道
            with patch("server.main.image_to_text", return_value="画面中有一张桌子"):
                ws.send_json({"type": "image", "image": fake_jpeg})
                r = ws.receive_json()
                assert r["type"] == "vlm_result"
                assert "桌子" in r["text"]

    def test_image_then_audio(self, client):
        """先发送画面再说话 — 验证顺序无关"""
        from unittest.mock import patch

        pcm_b64 = base64.b64encode(_make_pcm(0.5)).decode()
        fake_jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100).decode()

        with client.websocket_connect("/ws") as ws:
            with patch("server.main.image_to_text", return_value="画面中有一张桌子"):
                ws.send_json({"type": "image", "image": fake_jpeg})
                r = ws.receive_json()
                assert r["type"] == "vlm_result"

            with (
                patch("server.main.speech_to_text", return_value="用户说了什么"),
                patch(
                    "server.main.text_to_speech_stream",
                    return_value=_async_gen({"type": "audio", "audio": "", "is_final": True}),
                ),
            ):
                ws.send_json({"type": "audio", "audio": pcm_b64})
                r = ws.receive_json()
                assert r["type"] == "asr_result"
                ws.receive_json()  # text_result
                r = ws.receive_json()
                assert r["is_final"] is True

    def test_conversation_loop(self, client):
        """多轮对话: 音频→图片→音频→图片, 连续交互"""
        from unittest.mock import patch

        pcm_b64 = base64.b64encode(_make_pcm(0.5)).decode()
        fake_jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100).decode()

        with client.websocket_connect("/ws") as ws:
            for i in range(2):
                with (
                    patch("server.main.speech_to_text", return_value=f"第{i+1}轮"),
                    patch(
                        "server.main.text_to_speech_stream",
                        return_value=_async_gen({"type": "audio", "audio": "", "is_final": True}),
                    ),
                ):
                    ws.send_json({"type": "audio", "audio": pcm_b64})
                    r = ws.receive_json()
                    assert r["type"] == "asr_result"
                    ws.receive_json()  # text_result
                    r = ws.receive_json()
                    assert r["is_final"] is True

                with patch("server.main.image_to_text", return_value=f"第{i+1}轮画面"):
                    ws.send_json({"type": "image", "image": fake_jpeg})
                    r = ws.receive_json()
                    assert r["type"] == "vlm_result"

    def test_ping_still_works_in_mixed_flow(self, client):
        """非业务消息 echo 不受影响"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "ping", "msg": "hello"})
            r = ws.receive_json()
            assert r["type"] == "echo"
            assert r["data"]["msg"] == "hello"


class TestE2EErrorScenarios:
    """端到端错误场景"""

    def test_audio_then_vlm_both_fail(self, client):
        """ASR和VLM同时失败场景"""
        from unittest.mock import patch
        from server.asr import ASRError
        from server.vlm import VLMError

        pcm_b64 = base64.b64encode(_make_pcm(0.5)).decode()
        fake_jpeg = base64.b64encode(b"fake").decode()

        with client.websocket_connect("/ws") as ws:
            with patch("server.main.speech_to_text", side_effect=ASRError("asr fail")):
                ws.send_json({"type": "audio", "audio": pcm_b64})
                r = ws.receive_json()
                assert r["type"] == "error"
                assert "没听清" in r["message"]

            with patch("server.main.image_to_text", side_effect=VLMError("vlm fail")):
                ws.send_json({"type": "image", "image": fake_jpeg})
                r = ws.receive_json()
                assert r["type"] == "error"
                assert "图片分析失败" in r["message"]


def _async_gen(*items):
    async def gen():
        for item in items:
            yield item
    return gen()
