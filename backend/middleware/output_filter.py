import re
import time
import base64
import logging

logger = logging.getLogger(__name__)

FILTERED_MARKER = "[OUTPUT FILTERED: Potential system prompt leak detected]"


class OutputFilter:
    """Filters LLM responses to prevent system prompt leakage."""

    CONFIDENTIAL_MARKERS = [
        r"system\s*:",
        r"instructions\s*:",
        r"\[INST\]",
        r"<<SYS>>",
        r"<\|system\|>",
        r"<system>",
        r"### System Prompt",
        r"## Instructions",
    ]

    SELF_REFERENTIAL = [
        r"my\s+(instructions|system\s+prompt|hidden\s+prompt)\s+(are|is|says?|tells?)",
        r"i\s+was\s+(told|instructed|programmed)\s+to",
        r"my\s+system\s+prompt\s+says",
        r"(here\s+are|these\s+are)\s+my\s+(instructions|rules|guidelines)",
        r"i('m|\s+am)\s+instructed\s+to\s+(never|always|not)",
        r"my\s+(original|initial|hidden)\s+(instructions|prompt|message)",
    ]

    def filter(self, response_text: str, original_prompt: str = "") -> dict:
        start = time.time()
        filtered = response_text
        leaked = False
        leak_type = None

        # Check for confidential markers
        for pattern in self.CONFIDENTIAL_MARKERS:
            if re.search(pattern, filtered, re.IGNORECASE):
                leaked = True
                leak_type = "CONFIDENTIAL_MARKER"
                filtered = re.sub(
                    pattern + r".*?(?=\n\n|\Z)",
                    FILTERED_MARKER,
                    filtered,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                break

        # Check for self-referential leaks
        if not leaked:
            for pattern in self.SELF_REFERENTIAL:
                if re.search(pattern, filtered, re.IGNORECASE):
                    leaked = True
                    leak_type = "SELF_REFERENTIAL_LEAK"
                    # Replace the sentence containing the leak
                    sentences = filtered.split(". ")
                    cleaned = []
                    for s in sentences:
                        if re.search(pattern, s, re.IGNORECASE):
                            cleaned.append(FILTERED_MARKER)
                        else:
                            cleaned.append(s)
                    filtered = ". ".join(cleaned)
                    break

        # Check for base64-encoded content that might contain instructions
        if not leaked:
            b64_pattern = r"[A-Za-z0-9+/]{40,}={0,2}"
            b64_matches = re.findall(b64_pattern, filtered)
            for match in b64_matches:
                try:
                    decoded = base64.b64decode(match).decode("utf-8", errors="ignore")
                    suspicious_words = ["instruction", "system", "prompt", "ignore", "override"]
                    if any(word in decoded.lower() for word in suspicious_words):
                        leaked = True
                        leak_type = "ENCODED_LEAK"
                        filtered = filtered.replace(match, FILTERED_MARKER)
                        break
                except Exception:
                    pass

        elapsed = (time.time() - start) * 1000
        return {
            "filtered_text": filtered,
            "leaked": leaked,
            "leak_type": leak_type,
            "latency_ms": round(max(elapsed, 1), 1),
        }
