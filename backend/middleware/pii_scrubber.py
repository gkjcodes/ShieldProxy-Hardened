import re
import time
import logging

logger = logging.getLogger(__name__)

# Try to load spaCy for NER
_nlp = None
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    logger.info("spaCy NER model loaded")
except Exception:
    logger.info("spaCy unavailable — using regex-only PII scrubbing")


class PIIScrubber:
    """Detects and redacts PII using regex patterns + optional spaCy NER."""

    REGEX_PATTERNS = {
        "EMAIL": (
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            "[EMAIL REDACTED]",
        ),
        "SSN": (
            r"\b\d{3}-\d{2}-\d{4}\b",
            "[SSN REDACTED]",
        ),
        "CREDIT_CARD": (
            r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
            "[CARD REDACTED]",
        ),
        "PHONE": (
            r"(\+?1?\s?)?(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})",
            "[PHONE REDACTED]",
        ),
        "IP_ADDRESS": (
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            "[IP REDACTED]",
        ),
        "API_KEY": (
            r"(sk-|Bearer |AIza)[A-Za-z0-9_\-]{20,}",
            "[API_KEY REDACTED]",
        ),
    }

    NER_LABEL_MAP = {
        "PERSON": "[PERSON REDACTED]",
        "ORG": "[ORG REDACTED]",
        "GPE": "[LOCATION REDACTED]",
    }

    def scrub(self, text: str) -> dict:
        start = time.time()
        scrubbed = text
        pii_found = []

        # Regex-based PII detection
        for pii_type, (pattern, replacement) in self.REGEX_PATTERNS.items():
            matches = re.finditer(pattern, scrubbed)
            for match in matches:
                pii_found.append(
                    {
                        "type": pii_type,
                        "value_masked": match.group()[:3] + "***",
                        "position": match.start(),
                    }
                )
            scrubbed = re.sub(pattern, replacement, scrubbed)

        # spaCy NER-based detection (if available)
        if _nlp is not None:
            try:
                doc = _nlp(text)
                for ent in doc.ents:
                    if ent.label_ in self.NER_LABEL_MAP:
                        replacement = self.NER_LABEL_MAP[ent.label_]
                        if ent.text in scrubbed:
                            pii_found.append(
                                {
                                    "type": ent.label_,
                                    "value_masked": ent.text[:3] + "***",
                                    "position": ent.start_char,
                                }
                            )
                            scrubbed = scrubbed.replace(ent.text, replacement, 1)
            except Exception as e:
                logger.warning("spaCy NER failed: %s", e)

        elapsed = (time.time() - start) * 1000
        return {
            "scrubbed_text": scrubbed,
            "pii_found": pii_found,
            "pii_count": len(pii_found),
            "latency_ms": round(max(elapsed, 2), 1),
        }
