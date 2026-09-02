"""PII redaction for agent tool observations and exported text.

Complements ``utilities.redact`` (secret *keys*) by masking common personal
identifiers in free text before they leave the agent server (WebSocket events,
logs, trajectory exports).
"""

from __future__ import annotations

import re
from typing import Any

# Keep markers aligned with chat_interface/lib/pii-redact.ts
_SSN = re.compile(r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b")
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)"
)
_DOB_LABELED = re.compile(
    r"\b(?:dob|date\s*of\s*birth|born(?:\s+on)?)\s*[:\-]?\s*"
    r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
    re.I,
)
_DOB_NUMERIC = re.compile(
    r"\b(?:0?[1-9]|1[0-2])[\/\-](?:0?[1-9]|[12]\d|3[01])[\/\-](?:19|20)\d{2}\b"
)
_PASSPORT = re.compile(
    r"\b(?:passport(?:\s*(?:no|number|#))?)\s*[:\-]?\s*[A-Z0-9]{6,9}\b", re.I
)
_ROUTING = re.compile(
    r"\b(?:routing(?:\s*(?:no|number|#))?|aba)\s*[:\-]?\s*\d{9}\b", re.I
)
_BANK = re.compile(
    r"\b(?:account(?:\s*(?:no|number|#))?|acct)\s*[:\-]?\s*\d{6,17}\b", re.I
)
_CC_CANDIDATE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_IP = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"
)


def _luhn_ok(digits: str) -> bool:
    total = 0
    alt = False
    for ch in reversed(digits):
        n = ord(ch) - 48
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def _cc_sub(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 13 or len(digits) > 19:
        return raw
    # Chat ids are `chat-<unix-ms>-xxxx` — 13 ungrouped digits look like a PAN.
    if len(digits) == 13 and not re.search(r"[ -]", raw):
        return raw
    start = match.start()
    before = match.string[max(0, start - 5) : start]
    if re.search(r"chat-?$", before, re.I):
        return raw
    if not _luhn_ok(digits):
        return raw
    return f"[REDACTED:CREDIT_CARD]…{digits[-4:]}"


def redact_pii(text: str, *, keep_last4: bool = True) -> str:
    """Mask common PII patterns in free text."""
    if not text:
        return text

    def _digits(s: str) -> str:
        return re.sub(r"\D", "", s)

    out = text
    out = _SSN.sub(
        lambda m: (
            f"[REDACTED:SSN]…{_digits(m.group(0))[-4:]}"
            if keep_last4
            else "[REDACTED:SSN]"
        ),
        out,
    )
    out = _CC_CANDIDATE.sub(_cc_sub, out)
    out = _EMAIL.sub("[REDACTED:EMAIL]", out)
    out = _PHONE.sub(
        lambda m: (
            f"[REDACTED:PHONE]…{_digits(m.group(0))[-4:]}"
            if keep_last4
            else "[REDACTED:PHONE]"
        ),
        out,
    )
    out = _DOB_LABELED.sub("[REDACTED:DOB]", out)
    out = _DOB_NUMERIC.sub("[REDACTED:DOB]", out)
    out = _PASSPORT.sub("[REDACTED:PASSPORT]", out)
    out = _ROUTING.sub("[REDACTED:ROUTING]", out)
    out = _BANK.sub("[REDACTED:BANK_ACCOUNT]", out)
    out = _IP.sub("[REDACTED:IP]", out)
    return out


def redact_pii_deep(value: Any) -> Any:
    """Recursively redact string leaves in JSON-like structures."""
    if value is None:
        return value
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, list):
        return [redact_pii_deep(v) for v in value]
    if isinstance(value, dict):
        skip_keys = {"id", "linkedchatid", "externalref", "tool_call_id", "conversationid"}
        return {
            k: (v if str(k).lower() in skip_keys else redact_pii_deep(v))
            for k, v in value.items()
        }
    return value
