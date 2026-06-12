"""FastAPI WebSocket 入口 — AI 视觉对话助手"""

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.asr import ASRError, speech_to_text
from server.tts import TTSError, text_to_speech_stream

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Vision Dialogue", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket connected")
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "invalid json"})
                continue

            msg_type = data.get("type", "")

            if msg_type == "audio":
                await _handle_audio(ws, data)
            else:
                await ws.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


async def _handle_audio(ws: WebSocket, data: dict):
    """处理音频消息：ASR → TTS → 流式推送"""
    audio_b64 = data.get("audio", "")
    if not audio_b64:
        await ws.send_json({"type": "error", "message": "missing audio field"})
        return

    # 1. 语音识别
    try:
        text = speech_to_text(audio_b64)
    except ASRError:
        await ws.send_json(
            {"type": "error", "message": "抱歉，我没听清，请再说一次"}
        )
        return

    if not text.strip():
        await ws.send_json({"type": "error", "message": "未识别到语音内容"})
        return

    await ws.send_json({"type": "asr_result", "text": text})

    # 2. 语音合成 + 流式推送
    try:
        async for chunk in text_to_speech_stream(text):
            await ws.send_json(chunk)
    except TTSError:
        await ws.send_json(
            {"type": "error", "message": "抱歉，语音合成失败了"}
        )
