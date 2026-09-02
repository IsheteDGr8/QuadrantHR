# Incident Report Assistant — Backend

Backend + agent logic for incident intake: given a free-text incident
report, retrieves the best-matching company policy and generates a
follow-up question for HR to review before the ticket is submitted.

This is the backend/agent half only — no chat UI, forms, or HITL modal
(that's Person B's frontend, built against the contract below).

## Run locally

```
python -m venv venv
venv\Scripts\activate          # or: source venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python seed.py                 # creates incident_assistant.db, seeds 6 sample policies
uvicorn main:app --reload
```

Copy `.env.example` to `.env` and fill in `AZURE_OPENAI_*` to enable real
follow-up question generation. Without it, `POST /incident` still runs
end-to-end (retrieval + ticket creation) — it just returns `status:
"error"` instead of `"pending_review"`, which is useful for testing the
rest of the flow without an LLM key.

## Run tests

```
pytest tests/ -v
```

## API contract

### `POST /incident`

Request: `{ "incident_text": string }`

Response: `{ ticket_id, status, matched_policy_name, follow_up_question, error_message }`

`status` is one of:
- `"pending_review"` — matched a policy, follow-up question generated
- `"no_match"` — no policy matched the incident text
- `"error"` — matched a policy, but the LLM call failed (`error_message` populated)

Empty/missing `incident_text` → `HTTP 400`.

### `GET /ticket/{id}`

Returns the full ticket: `id, incident_summary, matched_policy_id,
matched_policy_name, follow_up_question, answer, status, created_at,
updated_at`.

### `POST /ticket/{id}/submit`

Request: `{ "answer": string, "confirmed": true }`

Response: `{ status, ticket_id }` — sets `status` to `"submitted"`.

## Design notes

- **Retrieval is keyword-overlap, not embeddings.** Tokenizes the incident
  text and each policy's name/category/related_keywords, scores by
  overlap. Deliberately simple for a small, hand-seeded policy set —
  swap for a real vector/embedding search if the policy set grows large
  enough that keyword overlap stops being reliable.
- **All JSON fields are snake_case**, matching the contract exactly — no
  field was renamed from the spec.
- **A ticket is always created**, even for `no_match` and `error` outcomes,
  so `ticket_id` is always returned and `GET /ticket/:id` always has
  something to fetch.
