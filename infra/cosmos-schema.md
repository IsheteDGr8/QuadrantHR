# Azure Cosmos DB — vector / conversational schema (Week 1 design)
# Local: use mock embeddings + in-process store until Cosmos is provisioned (Week 4).

## Containers (database: `quadranthr`)

### `chat_sessions`
Partition key: `/userId`  
Purpose: AI copilot + FAQ conversation memory

```json
{
  "id": "session-uuid",
  "userId": "user-uuid",
  "module": "copilot|faq",
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",
  "messages": [
    { "role": "user|assistant|tool", "content": "...", "ts": "ISO-8601" }
  ],
  "metadata": { "employeeId": "optional" }
}
```

### `knowledge_chunks`
Partition key: `/tenantId` (single-tenant: `"default"`)  
Purpose: RAG over policies / FAQ / SOPs  
Vector policy: cosine, dim TBD (1536 for Azure OpenAI ada-3-small; 8 for MockLLMProvider)

```json
{
  "id": "chunk-uuid",
  "tenantId": "default",
  "documentId": "blob-path-or-uuid",
  "source": "policies|faq|training",
  "title": "PTO Policy",
  "text": "chunk text...",
  "embedding": [0.1, 0.2],
  "acl": ["all", "hr"],
  "blobUri": "https://.../policies/pto.pdf"
}
```

### `training_attempts`
Partition key: `/employeeId`  
Purpose: flexible quiz results (Quizrant-shaped)

```json
{
  "id": "attempt-uuid",
  "employeeId": "employee-uuid",
  "moduleId": "course-slug",
  "score": 86.5,
  "passed": true,
  "answers": [{ "questionId": "...", "selected": "A" }],
  "completedAt": "ISO-8601"
}
```

## Local development without Cosmos
- `LLM_PROVIDER=mock` returns deterministic embeddings.
- Persist chat/RAG fixtures in Redis or local JSON until Azure subscription is live.
- Production: point `COSMOS_ENDPOINT` / `COSMOS_KEY` (Week 4).
