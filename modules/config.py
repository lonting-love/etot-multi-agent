import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"

SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "auto").strip().lower()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
BOCHA_API_KEY = os.getenv("BOCHA_API_KEY", "").strip()

MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "3"))
MAX_TOPIC_CHARS = int(os.getenv("MAX_TOPIC_CHARS", "500"))
MAX_QUERY_CHARS = int(os.getenv("MAX_QUERY_CHARS", "2000"))
RESEARCH_TIMEOUT_SECONDS = float(os.getenv("RESEARCH_TIMEOUT_SECONDS", "900"))
CHAT_TIMEOUT_SECONDS = float(os.getenv("CHAT_TIMEOUT_SECONDS", "180"))
RESEARCH_MAX_CONCURRENCY = int(os.getenv("RESEARCH_MAX_CONCURRENCY", "2"))
APP_API_KEY = os.getenv("APP_API_KEY", "").strip()

LOG_DIR = ROOT / "logs"


@lru_cache(maxsize=1)
def get_model():
    from langchain.chat_models import init_chat_model

    return init_chat_model(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY or None,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.1,
    )


def get_search_model():
    """检索与写作使用同一个 DeepSeek 模型，Web 搜索走 tools，而不是 OpenAI 专有参数。"""
    return get_model()
