"""应用配置，从环境变量加载"""

import os
from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_ASR_MODEL = os.getenv("DASHSCOPE_ASR_MODEL", "paraformer-realtime-v2")
DASHSCOPE_TTS_MODEL = os.getenv("DASHSCOPE_TTS_MODEL", "cosyvoice-v1")
DASHSCOPE_VLM_MODEL = os.getenv("DASHSCOPE_VLM_MODEL", "qwen-vl-max")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

ASR_TIMEOUT = int(os.getenv("ASR_TIMEOUT", "10"))
VLM_TIMEOUT = int(os.getenv("VLM_TIMEOUT", "15"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "10"))
TTS_TIMEOUT = int(os.getenv("TTS_TIMEOUT", "10"))

IMAGE_MAX_WIDTH = int(os.getenv("IMAGE_MAX_WIDTH", "512"))
IMAGE_MAX_HEIGHT = int(os.getenv("IMAGE_MAX_HEIGHT", "512"))
IMAGE_QUALITY = float(os.getenv("IMAGE_QUALITY", "0.7"))

VAD_SILENCE_THRESHOLD = float(os.getenv("VAD_SILENCE_THRESHOLD", "1.5"))

WS_MAX_MESSAGE_SIZE = int(os.getenv("WS_MAX_MESSAGE_SIZE", str(5 * 1024 * 1024)))
