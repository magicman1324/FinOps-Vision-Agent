"""测试 /ws WebSocket 端点"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _async_gen(*items):
    """Helper: 创建异步生成器"""
    async def gen():
        for item in items:
            yield item
    return gen()


def test_ws_echo(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "ping", "msg": "hello"})
        data = ws.receive_json()
        assert data["type"] == "echo"
        assert data["data"]["msg"] == "hello"


def test_ws_invalid_json(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_text("not valid json")
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "invalid json" in data["message"]


def test_audio_missing_field(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "audio"})
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "missing audio" in data["message"]


def test_audio_empty_text(client):
    with client.websocket_connect("/ws") as ws:
        with patch("server.main.speech_to_text", return_value="   "):
            ws.send_json({"type": "audio", "audio": "base64data"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "未识别" in data["message"]


def test_audio_asr_error(client):
    with client.websocket_connect("/ws") as ws:
        with patch("server.main.speech_to_text") as mock_asr:
            from server.asr import ASRError

            mock_asr.side_effect = ASRError("fail")
            ws.send_json({"type": "audio", "audio": "base64data"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "没听清" in data["message"]


def test_audio_pipeline(client):
    """完整音频管线：ASR → 文字回复 → TTS 流式推送"""
    with client.websocket_connect("/ws") as ws:
        with (
            patch("server.main.speech_to_text", return_value="你好"),
            patch(
                "server.main.text_to_speech_stream",
                return_value=_async_gen(
                    {"type": "audio", "audio": "bW9jaw==", "is_final": False},
                    {"type": "audio", "audio": "", "is_final": True},
                ),
            ),
        ):
            ws.send_json({"type": "audio", "audio": "base64data"})
            # 第1个: asr_result
            r1 = ws.receive_json()
            assert r1["type"] == "asr_result"
            assert r1["text"] == "你好"
            # 第2个: text_result (LLM 文字回复)
            r2 = ws.receive_json()
            assert r2["type"] == "text_result"
            assert r2["text"] == "mock response"  # autouse _mock_llm
            # 第3个: tts chunk
            r3 = ws.receive_json()
            assert r3["type"] == "audio"
            assert r3["audio"] == "bW9jaw=="
            assert r3["is_final"] is False
            # 第4个: tts final
            r4 = ws.receive_json()
            assert r4["type"] == "audio"
            assert r4["is_final"] is True
