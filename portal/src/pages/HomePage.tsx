import { MODULES } from "../modules";
import "./pages.css";

export function HomePage() {
  const live = MODULES.filter((m) => m.id !== "home" && m.status === "live");
  const soon = MODULES.filter((m) => m.status === "soon");

  return (
    <section className="page">
      <header className="page__hero">
        <p className="page__eyebrow">QuadrantHR</p>
        <h1 className="page__title">One portal for people operations</h1>
        <p className="page__lede">
          Seven hackathon modules, one shell. Directory is wired first; the rest
          plug in against the dockerized services on ports 8101–8107.
        </p>
      </header>

      <div className="page__grid">
        <article className="card">
          <h2>Live now</h2>
          <ul className="card__list">
            {live.map((m) => (
              <li key={m.id}>
                <strong>{m.label}</strong>
                <span>{m.blurb}</span>
              </li>
            ))}
          </ul>
        </article>
        <article className="card">
          <h2>Coming next</h2>
          <ul className="card__list">
            {soon.map((m) => (
              <li key={m.id}>
                <strong>{m.label}</strong>
                <span>
                  {m.blurb}
                  {m.servicePort ? ` · :${m.servicePort}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}
