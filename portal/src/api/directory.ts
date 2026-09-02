import type { Identity } from "../auth/session";

/** Proxied to Mel (Employee Directory) via Vite — see vite.config.ts */
const DIRECTORY_BASE =
  import.meta.env.VITE_DIRECTORY_API_BASE ?? "/api/directory";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function authHeaders(identity: Identity): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Dev-Role": identity.role,
    "X-Dev-User-Id": identity.id,
    "X-Dev-Name": identity.name,
  };
}

async function parseError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => null);
  const detail =
    typeof body?.detail === "string"
      ? body.detail
      : `${res.status} ${res.statusText}`;
  return new ApiError(res.status, detail);
}

export async function directoryLogin(
  email: string,
  password: string,
): Promise<Identity> {
  const res = await fetch(`${DIRECTORY_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw await parseError(res);
  const body = await res.json();
  return { id: body.id, role: body.role, name: body.name };
}

export type PersonHit = {
  id: string;
  name: string;
  title?: string | null;
  email?: string | null;
  org_unit?: string | null;
  office?: string | null;
};

export type DirectorySearchResult = {
  people?: PersonHit[];
  results?: PersonHit[];
  interpretation?: { rewritten_query?: string };
  [key: string]: unknown;
};

export async function directorySearch(
  identity: Identity,
  query: string,
): Promise<DirectorySearchResult> {
  const params = new URLSearchParams({
    query,
    view_mode: "work",
  });
  const res = await fetch(`${DIRECTORY_BASE}/search?${params}`, {
    headers: authHeaders(identity),
  });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function directoryHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${DIRECTORY_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
