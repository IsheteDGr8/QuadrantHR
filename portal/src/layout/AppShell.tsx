import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { MODULES } from "../modules";
import "./shell.css";

export function AppShell() {
  const { identity, signOut } = useAuth();

  return (
    <div className="shell">
      <aside className="shell__nav">
        <div className="shell__brand">
          <span className="shell__mark" aria-hidden>
            Q
          </span>
          <div>
            <p className="shell__product">QuadrantHR</p>
            <p className="shell__tag">Unified people ops</p>
          </div>
        </div>

        <nav className="shell__links" aria-label="Modules">
          {MODULES.map((mod) => (
            <NavLink
              key={mod.id}
              to={mod.path}
              end={mod.path === "/"}
              className={({ isActive }) =>
                `shell__link${isActive ? " shell__link--active" : ""}`
              }
            >
              <span>{mod.label}</span>
              {mod.status === "soon" ? (
                <span className="shell__badge">Soon</span>
              ) : null}
            </NavLink>
          ))}
        </nav>

        <div className="shell__footer">
          {identity ? (
            <>
              <p className="shell__user">{identity.name}</p>
              <p className="shell__meta">
                {identity.role} · {identity.email}
              </p>
              <button type="button" className="shell__signout" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <p className="shell__meta">Sign in from Directory to search people.</p>
          )}
        </div>
      </aside>

      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  );
}
