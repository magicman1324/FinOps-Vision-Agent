"""FastAPI WebSocket 入口 — AI 视觉对话助手"""

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.asr import ASRError, speech_to_text
from server.llm import LLMError, ask_llm
from server.router import classify_intent_l0
from server.tts import TTSError, text_to_speech_stream
from server.vlm import VLMError, image_to_text

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Vision Dialogue", version="0.2.0")

# 每连接最新画面缓存
_images: dict[int, str] = {}


def _cid(ws: WebSocket) -> int:
    return id(ws)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    cid = _cid(ws)
    logger.info("WebSocket connected cid=%d", cid)
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
            elif msg_type == "image":
                await _handle_visual(ws, data)
            else:
                await ws.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected cid=%d", cid)
    finally:
        _images.pop(cid, None)


async def _handle_audio(ws: WebSocket, data: dict):
    """音频: ASR → 意图路由 → VLM/LLM → TTS"""
    audio_b64 = data.get("audio", "")
    if not audio_b64:
        await ws.send_json({"type": "error", "message": "missing audio field"})
        return

    # 1. 语音识别
    try:
        text = speech_to_text(audio_b64)
    except ASRError:
        await ws.send_json({"type": "error", "message": "抱歉，我没听清，请再说一次"})
        return

    if not text.strip():
        await ws.send_json({"type": "error", "message": "未识别到语音内容"})
        return

    await ws.send_json({"type": "asr_result", "text": text})

    # 2. 意图分类 + 推理
    intent = classify_intent_l0(text)
    image = _images.get(_cid(ws))
    response = ""

    logger.info("intent=%s has_image=%s text=%r", intent, bool(image), text[:80])

    if intent == "visual" and image:
        response = await _vlm_answer(image, text)
    elif intent == "visual" and not image:
        response = "我还没看到画面，请将摄像头对准你想问的东西"
    else:
        response = await _llm_answer(text)

    # 3. TTS 语音合成
    try:
        async for chunk in text_to_speech_stream(response):
            await ws.send_json(chunk)
    except TTSError:
        await ws.send_json({"type": "error", "message": "抱歉，语音合成失败了"})


async def _handle_visual(ws: WebSocket, data: dict):
    """图片: 缓存最新帧 + VLM 描述"""
    image_b64 = data.get("image", "")
    if not image_b64:
        await ws.send_json({"type": "error", "message": "missing image field"})
        return

    _images[_cid(ws)] = image_b64

    prompt = data.get("prompt", "请描述你看到的画面")
    try:
        text = image_to_text(image_b64, prompt)
    except VLMError:
        await ws.send_json({"type": "error", "message": "抱歉，图片分析失败了"})
        return

    if not text.strip():
        await ws.send_json({"type": "error", "message": "未识别到画面内容"})
        return

    await ws.send_json({"type": "vlm_result", "text": text})


async def _vlm_answer(image: str, question: str) -> str:
    """VLM 根据画面回答用户问题"""
    prompt = f"用户正在看着画面，问你: {question}\n请根据你看到的画面内容，直接回答用户的问题。用中文回答，简洁一点。"
    try:
        return image_to_text(image, prompt)
    except VLMError:
        return "抱歉，图片分析失败了"


async def _llm_answer(question: str) -> str:
    """LLM 纯文本回答"""
    try:
        return await ask_llm(question)
    except LLMError:
        return "抱歉，我暂时无法回答这个问题"
