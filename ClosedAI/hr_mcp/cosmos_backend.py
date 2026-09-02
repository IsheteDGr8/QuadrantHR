"""Cosmos DB backend for hr-mcp employee lookups.

Uses the same account/database as the marketplace cosmos-db plugin, but is
spawned with the eager `hr` MCP server so a lookup does not depend on
activate_integration + a second LLM turn.
"""

from __future__ import annotations

import os
from typing import Any

from azure.cosmos import CosmosClient, exceptions


def _env(*names: str, default: str = "") -> str:
    for name in names:
        raw = os.environ.get(name)
        if not raw:
            continue
        value = raw.strip().strip('"').strip("'")
        if value and not value.startswith("gAAAAA") and not value.startswith("${"):
            return value
    return default


def _norm(doc: dict[str, Any]) -> dict[str, Any]:
    salary_obj = doc.get("compensation") if isinstance(doc.get("compensation"), dict) else {}
    salary = (
        salary_obj.get("annualSalary")
        if salary_obj
        else doc.get("annualSalary", doc.get("salary"))
    )
    pto = doc.get("ptoSnapshot") or doc.get("pto") or {}
    if pto:
        pto = {
            "accrual_days_per_year": pto.get("accrual_days_per_year", pto.get("accrualDaysPerYear")),
            "used_days": pto.get("used_days", pto.get("usedDays")),
            "remaining_days": pto.get("remaining_days", pto.get("remainingDays")),
            "as_of": pto.get("as_of", pto.get("asOf")),
        }
    benefits = doc.get("benefitsSnapshot") or doc.get("benefits") or {}
    work_auth = doc.get("workAuthorization") if isinstance(doc.get("workAuthorization"), dict) else {}
    return {
        "id": str(doc.get("employeeId") or doc.get("id") or ""),
        "name": doc.get("name") or "",
        "title": doc.get("jobTitle") or doc.get("role") or doc.get("title") or "",
        "department": doc.get("departmentName") or doc.get("department") or "",
        "email": doc.get("workEmail") or doc.get("email") or "",
        "manager": doc.get("managerName") or doc.get("manager") or "",
        "managerId": doc.get("managerId") or "",
        "location": doc.get("workLocationName") or doc.get("location") or "",
        "start_date": doc.get("hireDate") or doc.get("start_date") or "",
        "employment_type": doc.get("employmentType") or doc.get("employment_type") or "",
        "salary": salary,
        "currency": (salary_obj.get("currency") if salary_obj else None) or doc.get("currency") or "USD",
        "pay_frequency": (salary_obj.get("payFrequency") if salary_obj else None)
        or doc.get("pay_frequency")
        or "annual",
        "pto": pto or {
            "accrual_days_per_year": None,
            "used_days": None,
            "remaining_days": None,
            "as_of": None,
        },
        "benefits": benefits,
        "status": doc.get("employmentStatus") or doc.get("status") or "",
        "visaType": work_auth.get("visaType") or doc.get("visaType") or "",
    }


class CosmosBackend:
    """Read-only employee lookups against Azure Cosmos DB."""

    def __init__(self) -> None:
        uri = _env("COSMOS_URI", "COSMOS_ENDPOINT")
        key = _env("COSMOS_KEY")
        database = _env("COSMOS_DATABASE", "COSMOS_DATABASE_NAME", default="closedai-hr")
        container = _env("COSMOS_CONTAINER", "COSMOS_CONTAINER_NAME", default="employees")
        if not uri or not key:
            raise RuntimeError(
                "Cosmos backend requested but COSMOS_URI/COSMOS_ENDPOINT and "
                "COSMOS_KEY are missing from the MCP subprocess environment."
            )
        policies = _env(
            "COSMOS_POLICIES_CONTAINER",
            "COSMOS_POLICY_CONTAINER",
            default="reference",
        )
        self._client = CosmosClient(uri, credential=key)
        db = self._client.get_database_client(database)
        self._container = db.get_container_client(container)
        # closedai-hr stores policy docs in physical container `reference`
        # (logical name `policies` via recordType). A dedicated `policies`
        # container does not exist in this account — querying it 404s.
        self._policies_name = policies or "reference"
        self._reference = db.get_container_client(self._policies_name)
        self._cache: list[dict[str, Any]] | None = None
        self._db = db

    def _query(self, query: str, **params: Any) -> list[dict[str, Any]]:
        parameters = [{"name": f"@{k}", "value": v} for k, v in params.items()]
        try:
            return list(
                self._container.query_items(
                    query=query,
                    parameters=parameters or None,
                    enable_cross_partition_query=True,
                )
            )
        except exceptions.CosmosHttpResponseError as exc:
            raise RuntimeError(f"Cosmos query failed: {exc.status_code} {exc.message}") from exc

    def find_employee(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip()
        if not q:
            return None
        matches = self.find_employees(q)
        if not matches:
            return None
        lowered = q.lower()
        for emp in matches:
            if emp["id"].lower() == lowered or emp["name"].lower() == lowered:
                return emp
        return matches[0]

    def find_employees(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        sql = (
            f"SELECT TOP {int(limit)} * FROM c WHERE "
            "c.id = @raw OR c.employeeId = @raw "
            "OR CONTAINS(c.name, @raw, true) OR CONTAINS(c.workEmail, @raw, true) "
            "OR CONTAINS(c.email, @raw, true) "
            "OR CONTAINS(c.employeeId, @raw, true)"
        )
        docs = self._query(sql, raw=q)
        return [_norm(d) for d in docs]

    def _policy_container_clients(self):
        """Prefer `reference`, then a dedicated `policies` container if present."""
        names: list[str] = []
        primary = (self._policies_name or "reference").strip() or "reference"
        names.append(primary)
        if primary != "policies":
            names.append("policies")
        if primary != "reference":
            names.append("reference")
        seen: set[str] = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            yield name, self._db.get_container_client(name)

    def _query_policy_docs(self, query: str, **params: Any) -> list[dict[str, Any]]:
        parameters = [{"name": f"@{k}", "value": v} for k, v in params.items()]
        last_404: exceptions.CosmosHttpResponseError | None = None
        for _name, client in self._policy_container_clients():
            try:
                return list(
                    client.query_items(
                        query=query,
                        parameters=parameters or None,
                        enable_cross_partition_query=True,
                    )
                )
            except exceptions.CosmosHttpResponseError as exc:
                if exc.status_code == 404:
                    last_404 = exc
                    continue
                raise RuntimeError(
                    f"Cosmos policy query failed: {exc.status_code}"
                ) from exc
        if last_404 is not None:
            raise RuntimeError("Cosmos policy query failed: 404") from last_404
        return []

    def search_policies(self, query: str) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        # Physical container is `reference`. Policy entities are tagged with
        # recordType (policies, leave_policies, benefits_plans, …). Don't
        # require recordType on the first pass — some docs omit it.
        docs: list[dict[str, Any]] = []
        try:
            docs = self._query_policy_docs(
                "SELECT TOP 8 * FROM c WHERE "
                "(NOT IS_DEFINED(c.recordType) OR "
                "c.recordType IN ('policies', 'leave_policies', 'benefits_plans', "
                "'compliance_requirements', 'data_governance_policies', "
                "'knowledge_articles', 'document_templates')) "
                "AND (CONTAINS(c.title, @raw, true) "
                "OR CONTAINS(c.content, @raw, true) "
                "OR CONTAINS(c.summary, @raw, true) "
                "OR CONTAINS(c.category, @raw, true) "
                "OR CONTAINS(c.recordType, @raw, true))",
                raw=q,
            )
        except RuntimeError:
            docs = []
        if not docs:
            try:
                docs = self._query_policy_docs(
                    "SELECT TOP 40 * FROM c WHERE "
                    "NOT IS_DEFINED(c.recordType) OR "
                    "c.recordType IN ('policies', 'leave_policies', 'benefits_plans', "
                    "'compliance_requirements', 'data_governance_policies', "
                    "'knowledge_articles', 'document_templates')"
                )
            except RuntimeError:
                docs = []
        if not docs:
            try:
                docs = self._query_policy_docs("SELECT TOP 40 * FROM c")
            except RuntimeError as exc:
                raise RuntimeError(str(exc)) from exc
        terms = [t.lower() for t in q.replace("?", " ").split() if len(t) > 2]
        scored: list[tuple[int, dict[str, Any]]] = []
        for doc in docs:
            haystack = (
                f"{doc.get('title','')} {doc.get('summary','')} "
                f"{doc.get('content','')} {doc.get('category','')} "
                f"{doc.get('recordType','')}"
            ).lower()
            score = sum(haystack.count(t) for t in terms) if terms else 1
            if score:
                scored.append((score, {
                    "title": doc.get("title") or "",
                    "section": doc.get("category") or doc.get("policyId") or doc.get("recordType") or "",
                    "content": doc.get("summary") or doc.get("content") or "",
                    "source": doc.get("sourceDocument") or doc.get("policyId") or doc.get("id") or "reference",
                }))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Fall back to top documents even when no term overlaps, so the tool
        # returns grounded context instead of an empty result the agent retries.
        if not scored and docs:
            for doc in docs[:3]:
                scored.append((0, {
                    "title": doc.get("title") or "",
                    "section": doc.get("category") or doc.get("policyId") or doc.get("recordType") or "",
                    "content": doc.get("summary") or doc.get("content") or "",
                    "source": doc.get("sourceDocument") or doc.get("policyId") or doc.get("id") or "reference",
                }))
        return [doc for _, doc in scored[:3]]

    def all_employees(self) -> list[dict[str, Any]]:
        if self._cache is None:
            docs = self._query("SELECT * FROM c")
            self._cache = [_norm(d) for d in docs]
        return self._cache
