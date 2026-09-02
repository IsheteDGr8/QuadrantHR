import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  directoryHealth,
  directoryLogin,
  directorySearch,
  type PersonHit,
} from "../api/directory";
import { useAuth } from "../auth/AuthContext";
import "./pages.css";

function extractPeople(payload: unknown): PersonHit[] {
  if (!payload || typeof payload !== "object") return [];
  const obj = payload as Record<string, unknown>;
  const raw = (obj.results ?? obj.people) as unknown;
  if (!Array.isArray(raw)) return [];
  return raw.map((row) => {
    const p = row as Record<string, unknown>;
    const office = p.office;
    const officeName =
      typeof office === "string"
        ? office
        : office && typeof office === "object"
          ? String((office as { name?: string }).name ?? "")
          : "";
    return {
      id: String(p.id ?? ""),
      name: String(p.full_name ?? p.name ?? "Unknown"),
      title: (p.job_title as string | null | undefined) ?? (p.title as string | null | undefined) ?? null,
      email: (p.email as string | null | undefined) ?? null,
      org_unit: typeof p.org_unit === "string" ? p.org_unit : null,
      office: officeName || null,
    };
  });
}

export function DirectoryPage() {
  const { identity, signIn } = useAuth();
  const [email, setEmail] = useState("naomi.lewis@example.com");
  const [password, setPassword] = useState("orghub2026");
  const [query, setQuery] = useState("python engineer");
  const [people, setPeople] = useState<PersonHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [apiUp, setApiUp] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    directoryHealth().then((ok) => {
      if (!cancelled) setApiUp(ok);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onLogin(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const next = await directoryLogin(email.trim(), password);
      signIn(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    if (!identity) return;
    setBusy(true);
    setError(null);
    try {
      const payload = await directorySearch(identity, query.trim());
      setPeople(extractPeople(payload));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
      setPeople([]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page__hero">
        <p className="page__eyebrow">Directory · Mel</p>
        <h1 className="page__title">Find people across the org</h1>
        <p className="page__lede">
          Calls the Employee Directory API through the portal proxy. Mel’s own
          frontend is unchanged — this shell only consumes HTTP.
        </p>
        <p
          className={`page__status page__status--${apiUp === null ? "unknown" : apiUp ? "ok" : "down"}`}
        >
          API {apiUp === null ? "checking…" : apiUp ? "reachable" : "offline — start Mel or docker compose"}
        </p>
      </header>

      {!identity ? (
        <form className="card form" onSubmit={onLogin}>
          <h2>Demo sign-in</h2>
          <p className="form__hint">
            Uses Mel’s local demo auth (`AUTH_MODE=dev`). Sample HR user is
            prefilled.
          </p>
          <label>
            Email
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error ? <p className="form__error">{error}</p> : null}
          <button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      ) : (
        <>
          <form className="card form form--search" onSubmit={onSearch}>
            <h2>Search</h2>
            <label>
              Query
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="name, skill, team…"
                required
              />
            </label>
            {error ? <p className="form__error">{error}</p> : null}
            <button type="submit" disabled={busy || !query.trim()}>
              {busy ? "Searching…" : "Search directory"}
            </button>
          </form>

          <div className="results">
            {people.length === 0 ? (
              <p className="page__meta">No results yet — run a search.</p>
            ) : (
              people.map((person) => (
                <article key={person.id} className="result">
                  <h3>{person.name}</h3>
                  <p>{person.title || "No title on file"}</p>
                  <p className="page__meta">
                    {[person.org_unit, person.office, person.email]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </article>
              ))
            )}
          </div>
        </>
      )}
    </section>
  );
}
