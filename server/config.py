"""应用配置，从环境变量加载"""

import asyncio
import logging
import os
import sys

import dashscope
from dotenv import load_dotenv

load_dotenv()

# 清除系统代理 — dashscope/httpx 内部读 HTTP_PROXY 会走代理
for _key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_key, None)

# Windows: ProactorEventLoop SSL 兼容问题，切 Selector
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    logging.getLogger("config").warning("DASHSCOPE_API_KEY is empty — ASR/VLM/TTS will fail")
else:
    dashscope.api_key = DASHSCOPE_API_KEY

DASHSCOPE_ASR_MODEL = os.getenv("DASHSCOPE_ASR_MODEL", "fun-asr-realtime")
DASHSCOPE_TTS_MODEL = os.getenv("DASHSCOPE_TTS_MODEL", "cosyvoice-v1")
DASHSCOPE_VLM_MODEL = os.getenv("DASHSCOPE_VLM_MODEL", "qwen-vl-max")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

def _int_env(key: str, default: int) -> int:
    """读取整数环境变量，非法值时警告并回退默认"""
    val = os.getenv(key, str(default))
    try:
        return int(val)
    except ValueError:
        import logging
        logging.getLogger("config").warning(
            "%s=%r is not an integer, falling back to %d", key, val, default
        )
        return default


ASR_TIMEOUT = _int_env("ASR_TIMEOUT", 10)
VLM_TIMEOUT = _int_env("VLM_TIMEOUT", 15)
LLM_TIMEOUT = _int_env("LLM_TIMEOUT", 10)
TTS_TIMEOUT = _int_env("TTS_TIMEOUT", 10)

# IMAGE_* / VAD_SILENCE_THRESHOLD / WS_MAX_MESSAGE_SIZE 从未被消费，已移除。
# 图像压缩参数在 client/camera.js，VAD 在 client/vad.js，WS 大小由 uvicorn 控制。
