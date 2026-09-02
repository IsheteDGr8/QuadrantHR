import type { Identity } from "../auth/session";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => null);
  const detail =
    typeof body?.detail === "string"
      ? body.detail
      : `${res.status} ${res.statusText}`;
  return new ApiError(res.status, detail);
}

export async function login(email: string, password: string): Promise<Identity> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  // /auth/me for id — token payload is enough after login decode via me
  const meRes = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${body.access_token}` },
  });
  if (!meRes.ok) throw await parseError(meRes);
  const me = await meRes.json();
  return {
    id: me.id,
    role: body.role,
    name: body.full_name,
    email: body.email,
    accessToken: body.access_token,
  };
}

export type PersonHit = {
  id: string;
  name: string;
  title?: string | null;
  email?: string | null;
  org_unit?: string | null;
  office?: string | null;
};

export async function searchEmployees(
  identity: Identity,
  query: string,
): Promise<PersonHit[]> {
  const params = new URLSearchParams({ q: query, limit: "25" });
  const res = await fetch(`${API_BASE}/directory/employees?${params}`, {
    headers: { Authorization: `Bearer ${identity.accessToken}` },
  });
  if (!res.ok) throw await parseError(res);
  const rows = (await res.json()) as Array<{
    id: string;
    full_name: string;
    job_title?: string | null;
    work_email?: string | null;
    office?: string | null;
  }>;
  return rows.map((p) => ({
    id: p.id,
    name: p.full_name,
    title: p.job_title ?? null,
    email: p.work_email ?? null,
    office: p.office ?? null,
    org_unit: null,
  }));
}

export async function apiHealth(): Promise<boolean> {
  try {
    const res = await fetch("/health");
    return res.ok;
  } catch {
    return false;
  }
}
