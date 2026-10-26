import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
LOCAL_LLM_API_BASE = os.getenv("LOCAL_LLM_API_BASE", "http://localhost:11434/v1")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3")
