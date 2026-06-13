"""FastAPI WebSocket 入口 — AI 视觉对话助手"""

import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.asr import ASRError, speech_to_text
from server.llm import LLMError, ask_llm
from server.memory import ConversationMemory
from server.router import classify_intent_l0, classify_intent_l1
from server.tts import TTSError, text_to_speech_stream
from server.vlm import VLMError, image_to_text

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Vision Dialogue", version="0.3.1")

# 每连接状态
_images: dict[int, str] = {}
_memories: dict[int, ConversationMemory] = {}

# 三级降级链最终兜底文案
FALLBACK_PRESET = "抱歉，我暂时无法处理这个问题，请稍后再试"


def _cid(ws: WebSocket) -> int:
    return id(ws)


def _get_memory(ws: WebSocket) -> ConversationMemory:
    cid = _cid(ws)
    if cid not in _memories:
        _memories[cid] = ConversationMemory()
    return _memories[cid]


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
        _memories.pop(cid, None)


async def _handle_audio(ws: WebSocket, data: dict):
    """音频: ASR → 意图路由 → 三级降级推理 → TTS → 记忆"""
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

    # 2. 意图分类 (L0 正则 → L1 LLM 兜底) + 三级降级推理
    intent = classify_intent_l0(text)
    if intent == "textual":
        intent = await classify_intent_l1(text)
    image = _images.get(_cid(ws))
    memory = _get_memory(ws)

    logger.info("intent=%s has_image=%s turns=%d text=%r",
                intent, bool(image), memory.turn_count, text[:80])

    if intent == "visual" and image:
        response = await _cascade_visual(image, text, memory)
    elif intent == "visual" and not image:
        response = "我还没看到画面，请将摄像头对准你想问的东西"
    else:
        response = await _cascade_text(text, memory)

    # 3. 记入记忆 + 异步压缩
    memory.add_turn(text, response)
    if memory.mid_count > 0 and not memory.mid_compressed:
        asyncio.create_task(memory.compress_mid())
    if memory.mid_compressed and memory.mid_count >= 2:
        asyncio.create_task(memory.compress_background())

    # 4. TTS 语音合成
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


# ---- 三级降级链 ----

async def _cascade_visual(image: str, question: str, memory: ConversationMemory) -> str:
    """L1 VLM → L2 LLM → L3 预设文案"""
    ctx = memory.get_context()

    # L1: VLM
    prompt = f"用户正在看着画面，问你: {question}\n请根据你看到的画面内容，直接回答用户的问题。用中文回答，简洁一点。"
    if ctx:
        prompt = f"对话历史:\n{ctx}\n\n{prompt}"
    try:
        return image_to_text(image, prompt)
    except VLMError:
        logger.warning("VLM failed, cascading to LLM")

    # L2: LLM 兜底
    try:
        llm_prompt = (
            f"用户正在使用摄像头看东西，问: {question}\n"
            "你暂时看不到画面，但请根据常识尽量回答。如果你无法回答，请友好地告知用户。"
        )
        return await ask_llm(llm_prompt, system_prompt=ctx if ctx else None)
    except LLMError:
        logger.warning("LLM also failed, using preset fallback")

    # L3: 预设文案
    return FALLBACK_PRESET


async def _cascade_text(question: str, memory: ConversationMemory) -> str:
    """L1 LLM → L2 预设文案"""
    ctx = memory.get_context()

    # L1: LLM
    try:
        return await ask_llm(question, system_prompt=ctx if ctx else None)
    except LLMError:
        logger.warning("LLM failed, using preset fallback")

    # L2: 预设文案
    return FALLBACK_PRESET
