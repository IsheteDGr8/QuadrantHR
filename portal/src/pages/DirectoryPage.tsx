import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiHealth, login, searchEmployees, type PersonHit } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import "./pages.css";

export function DirectoryPage() {
  const { identity, signIn } = useAuth();
  const [email, setEmail] = useState("hr.admin@quadranthr.local");
  const [password, setPassword] = useState("changeme123");
  const [query, setQuery] = useState("engineer");
  const [people, setPeople] = useState<PersonHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [apiUp, setApiUp] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiHealth().then((ok) => {
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
      signIn(await login(email.trim(), password));
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
      setPeople(await searchEmployees(identity, query.trim()));
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
        <p className="page__eyebrow">Directory · unified backend</p>
        <h1 className="page__title">Find people across the org</h1>
        <p className="page__lede">
          Calls the modular monolith at <code>/api/v1/directory</code> (plan.md).
          Hackathon Mel code remains reference-only under <code>EmployeeDirectory/</code>.
        </p>
        <p
          className={`page__status page__status--${apiUp === null ? "unknown" : apiUp ? "ok" : "down"}`}
        >
          API {apiUp === null ? "checking…" : apiUp ? "reachable" : "offline — docker compose up"}
        </p>
      </header>

      {!identity ? (
        <form className="card form" onSubmit={onLogin}>
          <h2>Sign in</h2>
          <p className="form__hint">Seeded local JWT user (not Entra yet).</p>
          <label>
            Email
            <input value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
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
                    {[person.office, person.email].filter(Boolean).join(" · ")}
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
