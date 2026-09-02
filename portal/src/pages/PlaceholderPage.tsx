import { MODULES, type ModuleId } from "../modules";
import "./pages.css";

export function PlaceholderPage({ moduleId }: { moduleId: ModuleId }) {
  const mod = MODULES.find((m) => m.id === moduleId);
  if (!mod) return null;

  return (
    <section className="page">
      <header className="page__hero">
        <p className="page__eyebrow">Module stub</p>
        <h1 className="page__title">{mod.label}</h1>
        <p className="page__lede">
          {mod.blurb}. The backend already runs in compose
          {mod.servicePort ? ` on port ${mod.servicePort}` : ""}; this shell
          route will call it next without touching the team’s original repo.
        </p>
      </header>
      <article className="card card--notice">
        <p>
          Integration order: Directory → FAQ / Helpdesk → Hiring → Training /
          Policies → Copilot + MCP.
        </p>
      </article>
    </section>
  );
}
