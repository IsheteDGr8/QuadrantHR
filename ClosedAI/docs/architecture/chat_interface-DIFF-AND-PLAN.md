# chat_interface: MAIN vs SAFETY NET — Diff & Restore Plan

**Branches:** `main` (HEAD) vs `safety/eureka-pre-main-merge`  
**Goal:** Keep the new Vera UI / ui-block canvas where useful, but restore **orchestration behaviors** that made safety net responsive and reliable.

---

## Plan of work (how we do this)

1. **Document both architectures** → `chat_interface-MAIN.md`, `chat_interface-SAFETY-NET.md` (done).
2. **Diff orchestration-critical paths only** (not full UI chrome):
   - `lib/chat-store.ts`
   - `lib/canvas-store.ts` / canvas pipeline
   - `app/api/chat/route.ts` (prompt / agent settings)
   - Composer / conversation approval wiring
3. **Classify each delta:** must-restore (chat correctness/speed) vs UI-only keep vs obsolete.
4. **Integrate must-restore into main** without deleting `ui-block-canvas` wholesale.
5. **Verify:** send a simple headcount question; confirm no canvas HTTP spam; approval flow still works; no duplicate assistant bubbles.

---

## What changed (orchestration)

| Area | Safety net | Main (after UI merge) | Impact |
|------|------------|------------------------|--------|
| Canvas data path | Sync `ingestCanvas` from tool observations → `canvas-store` artifacts | LLM `canvas-server` + webhooks + **browser mirrors every WS event** | Main: extra HTTP + LLM work during turns → **slow / flaky** |
| `canvas-store` | Rich artifacts + `openApproval` | Thin open/width/count | Lost deterministic HR modules + canvas HITL |
| `pendingApproval` in chat-store | Present; composer gates send | **Removed** but composer still reads it | Broken send gating / undefined state |
| Skill activity | Keyword + invoke_skill helpers | Mostly removed | Weaker activity feed; harder to see agent progress |
| Assistant text | `upsertAssistant` + event-id dedupe | Mostly `appendAssistant`; weak dedupe | Duplicate/missed replies |
| Confirm waiting | Fallback to last tool step | Only last `running` step | Missed approval cards |
| System prompt | Mandatory `invoke_skill` | **FAST PATH** (better for simple lookups) | Main prompt is better for speed; keep it |
| `max_iterations` / MCP | 100 / hr-mcp | Same pattern | Shared backend cost |

---

## Must-restore into main (priority)

### P0 — Speed / hang risks
1. **Gate `mirrorEventToCanvas`** — only mirror Observation / agent Message / confirmation+terminal state updates (not every Action/think event).
2. **Restore `pendingApproval` + `approvalResolving`** on the store; set them when injecting approval; clear on approve/reject; keep composer gating working.
3. **Harden `waiting_for_confirmation`** — fall back to most recent tool-bearing activity step (safety behavior).

### P1 — Response correctness
4. Restore **`upsertAssistant`** for agent `MessageEvent`.
5. Restore **`seenEventIds`** dedupe (with skill re-paint exceptions as in safety).
6. Restore **skill activity helpers** + `matchKeywordSkills` on send + dedicated `invoke_skill` Action handling.

### P2 — Canvas product (optional follow-up)
7. Optionally reintroduce **sync artifact ingest** for structured HR tool JSON alongside ui-block canvas (hybrid), or keep LLM canvas but only on terminal turns.
8. Do **not** re-impose mandatory `invoke_skill` from safety prompt — keep main FAST PATH.

---

## Explicitly keep from main

- Vera branding / light theme UI
- `ui-block-canvas` + `canvas-server` (as a secondary surface), once traffic is gated
- FAST PATH / autonomy wording in `HR_SYSTEM_SUFFIX`
- Message-embedded approval cards in conversation (can coexist with `pendingApproval` flags)

---

## Integration checklist (this pass)

- [x] Architecture docs for MAIN + SAFETY NET
- [x] This plan file
- [x] P0+P1 patches in `lib/chat-store.ts` (+ conversation approval clear)
- [ ] Manual smoke: simple query fast; approval still confirms; canvas still opens without spamming

### Applied restore (2026-08-20)

In `chat_interface/lib/chat-store.ts` (+ `chat-conversation.tsx`):

1. Gated `mirrorEventToCanvas` (Observation / agent Message / confirm+terminal only)
2. Restored `pendingApproval` / `approvalResolving` + approve/reject actions; composer gating works again
3. Hardened waiting-for-confirmation fallback to last tool step
4. Restored `upsertAssistant`, `seenEventIds` dedupe, skill activity helpers + keyword match on send
5. Approval card clears store HITL flags on submit
