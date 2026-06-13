"""测试 VLM 模块"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from server.vlm import VLMError, image_to_text


class TestImageToText:
    def test_returns_text(self):
        fake_b64 = "ZmFrZWpwZWc="
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output.choices = [
            MagicMock(
                message=MagicMock(
                    content=[{"text": "这是一张包含猫的图片"}]
                )
            )
        ]

        with patch("server.vlm.MultiModalConversation") as MockMM:
            MockMM.call.return_value = mock_response
            result = asyncio.run(image_to_text(fake_b64))
            assert "猫" in result
            MockMM.call.assert_called_once()

    def test_uses_custom_prompt(self):
        fake_b64 = "ZmFrZWpwZWc="
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output.choices = [
            MagicMock(
                message=MagicMock(
                    content=[{"text": "红色汽车"}]
                )
            )
        ]

        with patch("server.vlm.MultiModalConversation") as MockMM:
            MockMM.call.return_value = mock_response
            result = asyncio.run(image_to_text(fake_b64, prompt="什么颜色的车?"))
            assert "红色" in result
            call_args = MockMM.call.call_args.kwargs
            messages = call_args["messages"]
            assert "什么颜色的车?" in messages[0]["content"][1]["text"]

    def test_raises_on_http_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.message = "Internal Error"

        with patch("server.vlm.MultiModalConversation") as MockMM:
            MockMM.call.return_value = mock_response
            with pytest.raises(VLMError, match="500"):
                asyncio.run(image_to_text("fake"))

    def test_raises_on_empty_choices(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output.choices = []

        with patch("server.vlm.MultiModalConversation") as MockMM:
            MockMM.call.return_value = mock_response
            with pytest.raises(VLMError, match="empty"):
                asyncio.run(image_to_text("fake"))
