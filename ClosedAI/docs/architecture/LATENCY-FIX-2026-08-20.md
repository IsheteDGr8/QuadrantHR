# Latency + MCP console-error fix (2026-08-20)

## Root cause (greeting took ~76s)

Conversation create registered canvas webhooks pointing at **`:3001`** while Next.js runs on **`:3000`**.

Backend `WebhookSubscriber` uses `event_buffer_size: 1` and **awaits** each POST (httpx timeout 30s × retries) on the agent event path. Streaming token events therefore blocked on connection-refused retries → multi-minute “hi” replies.

MCP “fetch failed” overlays were mostly **boot race** (UI loaded before `:8001` was ready) plus noisy `toast.error` / `console.error` on retry exhaustion.

## Fixes applied

1. **Env:** `FRONTEND_URL` / `CANVAS_WEBHOOK_BASE_URL` → `:3000`; `CANVAS_WEBHOOKS_ENABLED=false`.
2. **`app/api/chat/route.ts`:** webhooks empty unless explicitly enabled; if enabled, larger buffer + `num_retries: 0`.
3. **Greeting prompt:** one short sentence, zero tools.
4. **`mcp-store.tsx`:** soft-fail load/catalog (warn, no toast) so boot race does not spam the console overlay.
5. Browser canvas mirror in `chat-store` remains the local delivery path.

## Required to feel the fix

**Start a New Chat.** Old conversations still have the bad `:3001` webhook baked into their backend conversation record.
