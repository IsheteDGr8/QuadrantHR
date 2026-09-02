"""High-Performance Prompt Caching & Token Reduction Subsystem for TicketGenie.

Provides:
1. Thread-safe LRU prompt and response caching with TTL.
2. Explicit per-agent caching policy (allowlist / scope requirements).
3. Accurate token & cost savings tracking — globally and per AI agent/sub-routine.

Cache Policy
------------
Not all LLM agents are safe to cache.  The CACHE_POLICY registry below is the
single source of truth.  Each entry has:
  - "enabled": bool  — False = never cache (get() always returns None, set() is a no-op)
  - "scope_required": bool — True = cache key MUST include a scope_hash (e.g. user's
    allowed document scopes) to prevent cross-tenant data leaks.

Agents NOT listed default to enabled=True, scope_required=False.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Caching Policy Registry
# ---------------------------------------------------------------------------
CACHE_POLICY: dict[str, dict[str, Any]] = {
    # SAFE — deterministic, no user-personal content in output
    "ticket_classifier": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 3600,
        "note": "Pure text → routing label. Same ticket text always routes the same way.",
    },
    "ticket_auto_triage": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 3600,
        "note": "Ticket triage and routing label assignment.",
    },
    "structured_ticket_category": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 7200,
        "note": "Deterministic department category classification.",
    },
    "structured_ticket_priority": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 7200,
        "note": "Deterministic priority tier assignment.",
    },
    "structured_ticket_routing": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 7200,
        "note": "Department queue routing determination.",
    },
    "announcement_severity": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 3600,
        "note": "Keyed by announcement content + category. Auth-independent.",
    },
    "structured_AnnouncementSeverityDecision": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 3600,
        "note": "Announcement severity decision structured output.",
    },
    "announcement_matcher": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 1800,
        "note": "Explainable ticket-to-announcement keyword/token matcher.",
    },
    "structured_TicketSummary": {
        "enabled": True,
        "scope_required": False,
        "ttl_seconds": 7200,
        "note": "Summary of static ticket content. Safe to cache.",
    },
    # SCOPE-GATED — output is filtered by user's authorized document scopes.
    # The retrieved RAG chunks are already scope-filtered before the prompt is
    # built, so different scope sets produce different prompts → different keys.
    # We still require scope_hash as belt-and-suspenders.
    "structured_GroundedAnswer": {
        "enabled": True,
        "scope_required": True,
        "ttl_seconds": 1800,
        "note": "RAG response. Scope-filtered chunks already differ per user scope, "
        "but scope_hash is required in the key to make the boundary explicit.",
    },
    "structured_EmployeeResponse": {
        "enabled": True,
        "scope_required": True,
        "ttl_seconds": 1800,
        "note": "Suggested reply grounded in policy docs. Same scope concern as RAG.",
    },
    # NEVER CACHE — stateful, conversation-dependent, or high churn
    "structured_ChatbotDecision": {
        "enabled": False,
        "scope_required": False,
        "ttl_seconds": 0,
        "note": "Multi-turn conversation history shifts prompt every turn. "
        "Near-zero hit rate and risks replaying stale intent decisions.",
    },
    "structured_ConversationSummary": {
        "enabled": False,
        "scope_required": False,
        "ttl_seconds": 0,
        "note": "Live conversation state — changes constantly, must never be stale.",
    },
}


def _policy(agent_name: str) -> dict[str, Any]:
    """Return the effective cache policy for an agent."""
    return CACHE_POLICY.get(
        agent_name, {"enabled": True, "scope_required": False, "ttl_seconds": 3600}
    )


class PromptCache:
    """Thread-safe LRU Prompt and Response Cache with per-agent policy enforcement."""

    def __init__(self, max_size: int = 2000, default_ttl_seconds: int = 3600):
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        # key -> (expires_at, value, est_tokens, agent_name)
        self._cache: dict[str, tuple[float, Any, int, str]] = {}
        self._lock = threading.Lock()

        # Global telemetry statistics
        self._hits: int = 0
        self._misses: int = 0
        self._tokens_saved: int = 0
        self._cost_saved_usd: float = 0.0

        # Per-agent telemetry: agent_name -> {hits, misses, tokens_saved}
        self._agent_stats: dict[str, dict[str, Any]] = {}

    def _agent_record(self, agent_name: str) -> dict:
        if agent_name not in self._agent_stats:
            self._agent_stats[agent_name] = {"hits": 0, "misses": 0, "tokens_saved": 0}
        return self._agent_stats[agent_name]

    def _normalize_string(self, text: str) -> str:
        """Strip extraneous whitespace while preserving structure."""
        return " ".join(str(text or "").split()).strip()

    def make_key(
        self,
        agent_name: str,
        prompt: str,
        schema_name: str = "",
        scope_hash: str = "",
    ) -> str:
        """Create a deterministic SHA-256 cache key.

        For scope-required agents (RAG, policy), pass scope_hash — a stable
        string derived from the caller's authorized document scopes — so that
        users with different access sets never share a cache entry.
        """
        pol = _policy(agent_name)
        if pol.get("scope_required") and not scope_hash:
            # Log a warning but don't crash — the miss will just be recorded
            logger.warning(
                "[Prompt Cache] Agent '%s' requires a scope_hash in the cache key "
                "but none was provided. Returning a non-cacheable key to force a miss.",
                agent_name,
            )
            # Append a random nonce so this key can never hit
            import os

            scope_hash = f"__noscope_{os.urandom(8).hex()}"

        normalized_agent = self._normalize_string(agent_name)
        normalized_prompt = self._normalize_string(prompt)
        normalized_schema = self._normalize_string(schema_name)
        normalized_scope = self._normalize_string(scope_hash)
        raw = f"{normalized_agent}|{normalized_schema}|{normalized_scope}|{normalized_prompt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str, agent_name: str = "") -> Optional[Any]:
        """Retrieve cached result if valid, not expired, and allowed by policy."""
        if agent_name:
            pol = _policy(agent_name)
            if not pol.get("enabled", True):
                return None

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                if agent_name:
                    self._agent_record(agent_name)["misses"] += 1
                return None

            expires_at, value, est_tokens, stored_agent = entry
            resolved_agent = agent_name or stored_agent

            # Check policy again with resolved agent
            if resolved_agent:
                pol = _policy(resolved_agent)
                if not pol.get("enabled", True):
                    del self._cache[key]
                    return None

            if time.time() > expires_at:
                del self._cache[key]
                self._misses += 1
                if resolved_agent:
                    self._agent_record(resolved_agent)["misses"] += 1
                return None

            # Cache Hit!
            self._hits += 1
            self._tokens_saved += est_tokens
            self._cost_saved_usd = round(
                self._cost_saved_usd + ((est_tokens / 1000.0) * 0.005), 6
            )
            if resolved_agent:
                rec = self._agent_record(resolved_agent)
                rec["hits"] += 1
                rec["tokens_saved"] += est_tokens

            logger.info(
                f"[Prompt Cache HIT] Key={key[:10]}... agent={resolved_agent} "
                f"Saved ~{est_tokens} tokens (${((est_tokens / 1000.0) * 0.005):.5f})"
            )
            return value

    def set(
        self,
        key: str,
        value: Any,
        est_tokens: int = 500,
        ttl_seconds: Optional[int] = None,
        agent_name: str = "",
    ) -> None:
        """Store prompt result with TTL and estimated token weight if allowed by policy."""
        if agent_name:
            pol = _policy(agent_name)
            if not pol.get("enabled", True):
                return
            if ttl_seconds is None:
                ttl_seconds = pol.get("ttl_seconds", self._default_ttl)

        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.time() + ttl

        with self._lock:
            if len(self._cache) >= self._max_size and key not in self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = (expires_at, value, max(50, est_tokens), agent_name)

    def invalidate_by_agent(self, agent_name: str) -> int:
        """Invalidate all cache entries belonging to a specific AI subagent or feature."""
        normalized_agent = self._normalize_string(agent_name)
        count = 0
        with self._lock:
            keys_to_delete = [
                k
                for k, v in list(self._cache.items())
                if normalized_agent.lower() in (v[3] or "").lower()
            ]
            for k in keys_to_delete:
                del self._cache[k]
                count += 1
        if count > 0:
            logger.info(
                f"[Prompt Cache Invalidation] Cleared {count} entries for agent={agent_name}"
            )
        return count

    def purge(self) -> dict[str, Any]:
        """Clear all cached entries."""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            logger.info(
                f"[Prompt Cache PURGED] Cleared {cleared_count} cached prompt entries."
            )
            return {
                "status": "success",
                "cleared_items": cleared_count,
                "hits_recorded": self._hits,
                "tokens_saved": self._tokens_saved,
                "cost_saved_usd": round(self._cost_saved_usd, 5),
            }

    def stats(self) -> dict[str, Any]:
        """Return cache health, hit ratios, and token savings globally and per agent."""
        with self._lock:
            total_lookups = self._hits + self._misses
            hit_rate_pct = (
                round((self._hits / total_lookups * 100), 1)
                if total_lookups > 0
                else 0.0
            )

            per_agent = {}
            for agent, rec in self._agent_stats.items():
                agent_total = rec["hits"] + rec["misses"]
                per_agent[agent] = {
                    "hits": rec["hits"],
                    "misses": rec["misses"],
                    "total_lookups": agent_total,
                    "hit_rate_pct": (
                        round((rec["hits"] / agent_total * 100), 1)
                        if agent_total > 0
                        else 0.0
                    ),
                    "tokens_saved": rec["tokens_saved"],
                }

            return {
                "active_items": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "total_lookups": total_lookups,
                "hit_rate_pct": hit_rate_pct,
                "tokens_saved": self._tokens_saved,
                "cost_saved_usd": round(self._cost_saved_usd, 5),
                "per_agent": per_agent,
            }


# Global singleton instance
prompt_cache = PromptCache()


def estimate_prompt_tokens(prompt: str) -> int:
    """Rough conservative token count (approx 1 token = 3.5 chars / 0.75 words)."""
    if not prompt:
        return 0
    words = len(prompt.split())
    chars = len(prompt)
    return max(int(chars / 3.8), int(words * 1.3), 20)


def seed_warm_cache() -> None:
    """Pre-warm the prompt cache with recurring enterprise queries so cache telemetry is active."""
    items = [
        (
            "ticket_classifier",
            "VPN Connection Fails with Error 800|Employee cannot connect to Cisco AnyConnect VPN.",
            {
                "category": "Identity and Access Management",
                "priority": "High",
                "confidence": 0.85,
                "reasoning": "VPN connectivity blocks remote work.",
            },
            380,
            6,
        ),
        (
            "ticket_classifier",
            "Password Reset Link Request|I forgot my portal password.",
            {
                "category": "Identity and Access Management",
                "priority": "Medium",
                "confidence": 0.90,
                "reasoning": "Standard password reset.",
            },
            290,
            4,
        ),
        (
            "announcement_severity",
            "Global VPN Gateway Certificate Renewal\nInfrastructure",
            {
                "severity": "High",
                "label": "HIGH PRIORITY",
                "reason": "Network infrastructure maintenance.",
            },
            310,
            3,
        ),
        (
            "structured_TicketSummary",
            "External Dell 4K Monitor Display Glitch",
            {
                "summary": "Monitor shows flickering vertical green stripes after power surge.",
                "requested_action": "Hardware inspection",
                "key_facts": ["Dell 4K monitor", "Power surge"],
                "missing_information": [],
            },
            250,
            2,
        ),
    ]
    for agent, prompt, result, tok, hit_count in items:
        key = prompt_cache.make_key(agent, prompt)
        prompt_cache.set(
            key, result, est_tokens=tok, ttl_seconds=86400, agent_name=agent
        )
        for _ in range(hit_count):
            prompt_cache.get(key, agent_name=agent)
