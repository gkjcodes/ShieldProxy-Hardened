import re
import time
import random
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class ThreatClassifier:
    """
    High-accuracy threat classifier using local/remote LLM with regex fallback.
    Non-blocking async execution without import-time network hangs.
    """

    VALID_CATEGORIES = [
        "PROMPT_INJECTION", "JAILBREAK",
        "SYSTEM_PROMPT_LEAK", "SOCIAL_ENGINEERING", "SAFE"
    ]

    PATTERNS = {
        "PROMPT_INJECTION": [
            (r"ignore\s+(all\s+|previous\s+|above\s+|prior\s+)?(instructions|rules|prompts|context)", 3),
            (r"disregard\s+(your|all|the)\s+(training|instructions|guidelines)", 3),
            (r"new\s+(instruction|directive|rule|task)\s*:", 2),
            (r"override\s+(your\s+)?(system|safety|previous)", 3),
            (r"you\s+are\s+now\s+(a|an|the)\s+", 2),
            (r"act\s+as\s+(a|an|the|if)\s+", 1.5),
            (r"pretend\s+(you\s+are|to\s+be|that)", 2),
            (r"forget\s+(everything|all|what|your)", 3),
            (r"do\s+not\s+(follow|apply|use)\s+(your\s+)?(safety|guidelines|rules)", 3),
            (r"system\s*prompt\s*:?", 2),
            (r"from\s+now\s+on\s+(you|your|ignore)", 2),
            (r"stop\s+being\s+(a\s+)?(helpful|safe|responsible)", 2),
            (r"(?:new|real|actual|true)\s+(?:role|persona|identity)\s*(?:is|:)", 2),
            (r"respond\s+as\s+(?:if|though)\s+you", 2),
        ],
        "JAILBREAK": [
            (r"(DAN|jailbreak|developer\s+mode|god\s+mode|unrestricted\s+mode)", 3),
            (r"no\s+(restrictions|filters|limits|rules|guidelines|safety)", 2),
            (r"(bypass|disable|remove|turn\s+off)\s+(your\s+)?(safety|filter|restriction|guideline)", 3),
            (r"you\s+(must|have\s+to|should)\s+(obey|comply|follow)\s+(me|my|all)", 2),
            (r"(evil|unethical|harmful|dangerous)\s+(mode|version|persona)", 3),
            (r"respond\s+without\s+(any\s+)?(restriction|filter|safety|limit)", 2),
            (r"(unlock|enable)\s+(full|unrestricted|complete)\s+(access|mode|capability)", 2.5),
            (r"do\s+anything\s+now", 2),
        ],
        "SYSTEM_PROMPT_LEAK": [
            (r"(reveal|show|print|display|tell\s+me|repeat|output|dump)\s+(your\s+|the\s+)?(system|initial|original|hidden|secret|full)\s+(prompt|instructions|context|message)", 3),
            (r"what\s+(are|were|is)\s+your\s+(initial|original|system|hidden)\s+(instructions|prompt|context)", 3),
            (r"(above|previous|initial|original)\s+(conversation|message|context|prompt|instruction)", 2),
            (r"(summarize|describe|explain)\s+(your|the)\s+(system|initial|original)\s+(prompt|instruction)", 2),
            (r"copy\s+(your|the)\s+(system|initial|hidden)\s+(prompt|message|instruction)", 2.5),
            (r"(beginning|start)\s+of\s+(this|the|your)\s+(conversation|chat|session)", 1.5),
            (r"tell\s+me\s+(ur|your)\s+(instructions|rules|prompt|guidelines|core|source)", 3),
            (r"(can\s+u|can\s+you)\s+tell\s+me\s+.{0,30}(instructions|rules|prompt|source)", 3),
            (r"(share|give\s+me|let\s+me\s+see)\s+(your|ur)\s+(instructions|rules|prompt|code|source)", 3),
            (r"(your|ur)\s+(core|source|internal|hidden|inner)\s+(instructions|code|prompt|logic|rules)", 3),
            (r"(what|how)\s+(are|is)\s+(your|ur)\s+(instructions|rules|guidelines|prompt)", 2.5),
            (r"(show|reveal|leak|expose)\s+.{0,20}(instructions|source\s+code|prompt|rules)", 2.5),
            (r"(read|access|view)\s+(your|the)\s+(source|code|instructions|prompt)", 2.5),
            (r"tell\s+me\s+.{0,40}(source|instructions|rules|prompt|code)", 2),
            (r"(i\s+want|i\s+need)\s+.{0,30}(instructions|source|prompt|rules|code)", 2),
        ],
        "SOCIAL_ENGINEERING": [
            (r"(my|our)\s+(life|job|career|family)\s+(depends|is\s+at\s+risk|will\s+be\s+ruined)", 2),
            (r"(emergency|urgent|critical|life.or.death)", 1.5),
            (r"i\s+will\s+(die|be\s+fired|be\s+hurt)", 2),
            (r"please\s+help\s+me\s+(hack|bypass|override|break)", 2),
            (r"(you\s+(owe|must\s+help)|it('s|\s+is)\s+(your|the)\s+(duty|job|responsibility)\s+to)", 2),
            (r"i('m|\s+am)\s+(testing|a\s+researcher|a\s+developer|from\s+anthropic|from\s+openai)", 1.5),
            (r"(trust\s+me|believe\s+me|i\s+promise)", 1),
            (r"(admin|administrator|root)\s+(access|privilege|override)", 2),
            (r"(make\s+u|make\s+you)\s+(a\s+)?(friend|happy|feel\s+better)", 1.5),
            (r"(won'?t\s+feel\s+alone|be\s+my\s+friend|i'?m\s+your\s+friend)", 1.5),
            (r"(just\s+between\s+us|our\s+secret|don'?t\s+tell\s+anyone)", 2),
            (r"(you\s+can\s+trust\s+me|i('m|\s+am)\s+friendly|we'?re\s+friends)", 1.5),
            (r"(help\s+me\s+out|do\s+me\s+a\s+favor)\s+.{0,20}(instructions|rules|prompt|code)", 2),
        ],
    }

    def __init__(self, use_mock: Optional[bool] = None):
        self.use_mock = settings.USE_MOCK_LLM if use_mock is None else use_mock
        self.model = settings.LOCAL_LLM_MODEL
        self._async_client = None
        self._cache = {}

        if not self.use_mock:
            try:
                from openai import AsyncOpenAI
                self._async_client = AsyncOpenAI(
                    base_url=settings.LOCAL_LLM_API_BASE,
                    api_key="local-ignore",
                    timeout=settings.GATEWAY_TIMEOUT_SECONDS,
                )
                logger.info("🧠 ThreatClassifier initialized with AsyncOpenAI (%s)", self.model)
            except Exception as e:
                logger.warning("ThreatClassifier async client init failed: %s", e)

    async def classify(self, text: str) -> dict:
        start = time.time()

        if self._async_client is not None and not self.use_mock:
            try:
                llm_result = await self._ollama_classify(text, start)
                llm_result["inference_time_ms"] = round((time.time() - start) * 1000, 1)
                return llm_result
            except Exception as e:
                logger.warning("Ollama inference failed: %s — falling back to regex", e)

        regex_result = self._regex_classify(text)
        regex_result["inference_time_ms"] = round((time.time() - start) * 1000, 1)
        return regex_result

    async def _ollama_classify(self, text: str, start: float) -> dict:
        if text in self._cache:
            cached_result = self._cache[text].copy()
            cached_result["model"] = f"{self.model} (cached)"
            return cached_result

        system_msg = (
            "You are a cybersecurity threat classifier for an LLM firewall. "
            "Analyze the user prompt for security threats. "
            "Respond with ONLY one word from: SAFE, PROMPT_INJECTION, JAILBREAK, SYSTEM_PROMPT_LEAK, SOCIAL_ENGINEERING."
        )

        response = await self._async_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f'Classify this prompt: "{text}"'},
            ],
            max_tokens=15,
            temperature=0.0,
        )

        output = response.choices[0].message.content.strip().upper()
        elapsed = (time.time() - start) * 1000

        detected_type = "SAFE"
        for category in self.VALID_CATEGORIES:
            if category in output:
                detected_type = category
                break

        is_threat = detected_type != "SAFE"
        result = {
            "is_threat": is_threat,
            "threat_type": detected_type,
            "confidence": 0.95 if is_threat else 0.90,
            "matched_patterns": [],
            "inference_time_ms": round(elapsed, 1),
            "model": self.model,
        }
        self._cache[text] = result
        return result.copy()

    def _regex_classify(self, text: str) -> dict:
        text_lower = text.lower().strip()
        scores = {}
        all_matched = {}

        for threat_type, patterns in self.PATTERNS.items():
            score = 0.0
            matched = []
            for pattern, weight in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    score += weight
                    clean_label = re.sub(r"[\\()|?+*\[\]{}^$.]", "", pattern)
                    clean_label = clean_label.replace("\\s+", " ").replace("\\s*", "")[:50]
                    matched.append(clean_label)
            scores[threat_type] = score
            all_matched[threat_type] = matched

        max_type = max(scores, key=scores.get)
        max_score = scores[max_type]

        if max_score >= 1.0:
            is_threat = True
            confidence = min(0.5 + (max_score * 0.1), 0.98)
        else:
            max_type = "SAFE"
            is_threat = False
            confidence = 0.92

        return {
            "is_threat": is_threat,
            "threat_type": max_type,
            "confidence": round(confidence, 2),
            "matched_patterns": all_matched.get(max_type, []),
            "inference_time_ms": 0,
            "model": "regex_fallback",
        }