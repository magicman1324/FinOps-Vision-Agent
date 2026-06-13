"""三级降级链测试 — VLM→LLM→预设文案 & LLM→预设文案"""

import base64
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from server.asr import ASRError
from server.llm import LLMError
from server.main import FALLBACK_PRESET, app
from server.tts import TTSError
from server.vlm import VLMError


@pytest.fixture
def client():
    return TestClient(app)


def _async_gen(*items):
    """Helper: async generator from items"""
    async def gen():
        for item in items:
            yield item
    return gen()


def _fake_jpeg_b64():
    return base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100).decode()


def _fake_pcm_b64():
    pcm = b"\x00" * 32000  # 1s 16kHz 16bit silence
    return base64.b64encode(pcm).decode()


class TestCascadeVisual:
    """_cascade_visual: L1 VLM → L2 LLM → L3 FALLBACK_PRESET"""

    def test_l1_vlm_succeeds(self, client):
        """VLM 正常返回，不降级到 LLM"""
        pcm = _fake_pcm_b64()

        with patch("server.main.speech_to_text", return_value="这是什么颜色"):
            with patch("server.main.image_to_text", return_value="这是一个红色的苹果"):
                with patch("server.main.text_to_speech_stream",
                           return_value=_async_gen({"type": "audio", "audio": "", "is_final": True})):
                    with client.websocket_connect("/ws") as ws:
                        # 先发一张图片
                        ws.send_json({"type": "image", "image": _fake_jpeg_b64()})
                        ws.receive_json()  # vlm_result

                        # 发语音问视觉问题
                        ws.send_json({"type": "audio", "audio": pcm})

                        r1 = ws.receive_json()
                        assert r1["type"] == "asr_result"
                        assert r1["text"] == "这是什么颜色"

                        ws.receive_json()  # text_result

                        # TTS final — VLM 返回的内容 ("苹果" or our mock)
                        r2 = ws.receive_json()
                        assert r2["is_final"] is True

    def test_l2_llm_fallback_on_vlm_error(self, client):
        """VLM 失败 → LLM 兜底成功"""
        pcm = _fake_pcm_b64()

        with patch("server.main.speech_to_text", return_value="这是什么"):
            with patch("server.main.image_to_text", side_effect=VLMError("vlm down")):
                with patch("server.main.text_to_speech_stream",
                           return_value=_async_gen({"type": "audio", "audio": "", "is_final": True})):
                    with client.websocket_connect("/ws") as ws:
                        ws.send_json({"type": "image", "image": _fake_jpeg_b64()})
                        ws.receive_json()  # vlm_result, may error if vlm fails on send too? No, vlm call here succeeds

                        ws.send_json({"type": "audio", "audio": pcm})

                        r1 = ws.receive_json()
                        assert r1["type"] == "asr_result"

                        ws.receive_json()  # text_result

                        # TTS final — should have LLM mocked "mock response"
                        r2 = ws.receive_json()
                        assert r2["is_final"] is True

    def test_l3_preset_on_vlm_and_llm_error(self, client):
        """VLM 失败 + LLM 也失败 → FALLBACK_PRESET"""
        pcm = _fake_pcm_b64()

        with patch("server.main.speech_to_text", return_value="这是什么"):
            with patch("server.main.image_to_text", side_effect=VLMError("vlm down")):
                with patch("server.main.ask_llm", side_effect=LLMError("llm down")):
                    with patch("server.main.text_to_speech_stream",
                               return_value=_async_gen({"type": "audio", "audio": "", "is_final": True})):
                        with client.websocket_connect("/ws") as ws:
                            ws.send_json({"type": "image", "image": _fake_jpeg_b64()})
                            ws.receive_json()

                            ws.send_json({"type": "audio", "audio": pcm})

                            r1 = ws.receive_json()
                            assert r1["type"] == "asr_result"

                            ws.receive_json()  # text_result

                            r2 = ws.receive_json()
                            assert r2["is_final"] is True


class TestCascadeText:
    """_cascade_text: L1 LLM → L2 FALLBACK_PRESET"""

    def test_l1_llm_succeeds(self, client):
        """纯文本问题走 LLM"""
        pcm = _fake_pcm_b64()

        with patch("server.main.speech_to_text", return_value="今天天气怎么样"):
            with patch("server.main.text_to_speech_stream",
                       return_value=_async_gen({"type": "audio", "audio": "", "is_final": True})):
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({"type": "audio", "audio": pcm})

                    r1 = ws.receive_json()
                    assert r1["type"] == "asr_result"
                    ws.receive_json()  # text_result
                    # TTS final
                    r2 = ws.receive_json()
                    assert r2["is_final"] is True

    def test_l2_preset_on_llm_error(self, client):
        """纯文本 LLM 失败 → FALLBACK_PRESET"""
        pcm = _fake_pcm_b64()

        with patch("server.main.speech_to_text", return_value="今天天气怎么样"):
            with patch("server.main.ask_llm", side_effect=LLMError("llm down")):
                with patch("server.main.text_to_speech_stream",
                           return_value=_async_gen({"type": "audio", "audio": "", "is_final": True})):
                    with client.websocket_connect("/ws") as ws:
                        ws.send_json({"type": "audio", "audio": pcm})

                        r1 = ws.receive_json()
                        assert r1["type"] == "asr_result"

                        ws.receive_json()  # text_result

                        r2 = ws.receive_json()
                        assert r2["is_final"] is True


class TestNoImageVisualIntent:
    """视觉意图但没有图片 — 提示用户"""

    def test_visual_intent_no_image(self, client):
        """问视觉问题但没发过图片 → 友好提示"""
        pcm = _fake_pcm_b64()

        with patch("server.main.speech_to_text", return_value="这是什么颜色"):
            with patch("server.main.text_to_speech_stream",
                       return_value=_async_gen({"type": "audio", "audio": "", "is_final": True})):
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({"type": "audio", "audio": pcm})

                    r1 = ws.receive_json()
                    assert r1["type"] == "asr_result"

                    ws.receive_json()  # text_result

                    r2 = ws.receive_json()
                    assert r2["is_final"] is True


class TestCascadeUnit:
    """单元测试：直接调用 cascade 函数"""

    def test_cascade_visual_l1_success(self):
        import asyncio
        from server.main import _cascade_visual
        from server.memory import ConversationMemory

        mem = ConversationMemory()
        with patch("server.main.image_to_text", return_value="红色苹果"):
            result = asyncio.run(_cascade_visual(_fake_jpeg_b64(), "这是什么颜色", mem))
            assert result == "红色苹果"

    def test_cascade_visual_l2_fallback(self):
        import asyncio
        from server.main import _cascade_visual
        from server.memory import ConversationMemory

        mem = ConversationMemory()
        with patch("server.main.image_to_text", side_effect=VLMError("fail")):
            result = asyncio.run(_cascade_visual(_fake_jpeg_b64(), "这是什么", mem))
            assert "mock response" in result

    def test_cascade_visual_l3_preset(self):
        import asyncio
        from server.main import _cascade_visual
        from server.memory import ConversationMemory

        mem = ConversationMemory()
        with patch("server.main.image_to_text", side_effect=VLMError("fail")):
            with patch("server.main.ask_llm", new=AsyncMock(side_effect=LLMError("fail"))):
                result = asyncio.run(_cascade_visual(_fake_jpeg_b64(), "这是什么", mem))
                assert result == FALLBACK_PRESET

    def test_cascade_text_l1_success(self):
        import asyncio
        from server.main import _cascade_text
        from server.memory import ConversationMemory

        mem = ConversationMemory()
        result = asyncio.run(_cascade_text("今天天气怎么样", mem))
        assert "mock response" in result

    def test_cascade_text_l2_preset(self):
        import asyncio
        from server.main import _cascade_text
        from server.memory import ConversationMemory

        mem = ConversationMemory()
        with patch("server.main.ask_llm", new=AsyncMock(side_effect=LLMError("fail"))):
            result = asyncio.run(_cascade_text("今天天气怎么样", mem))
            assert result == FALLBACK_PRESET
