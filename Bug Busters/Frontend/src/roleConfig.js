// Maps a role string to which dashboard a signed-in user lands on.
//
// These four are the complete, fixed role set - see
// backend/demo_login_db.py's CHECK constraint. Real Entra login (which
// would have sourced this from account.idTokenClaims.roles) has been
// removed from the project; the demo login endpoint (POST /demo-login)
// is now the only sign-in path and returns one of these four exactly.
export const ROLE_TO_DASHBOARD = {
  HR: "hr",
  Manager: "manager",
  Engineer: "engineer",
  Intern: "employee",
};

// A user can hold zero, one, or multiple app roles. When there's more than
// one dashboard match, this order decides which one wins — adjust if the
// intended precedence differs (e.g. someone who is both Manager and HR).
const DASHBOARD_PRIORITY = ["hr", "manager", "engineer", "employee"];

// Returns which dashboard key ("hr" | "manager" | "engineer" | "employee")
// a set of Entra roles should land on, or null if none of the caller's
// roles map to anything — the null case is the "access denied / no role
// assigned" fallback, not a crash.
export function resolveDashboard(roles) {
  if (!Array.isArray(roles) || roles.length === 0) return null;

  const matched = roles
    .map((role) => ROLE_TO_DASHBOARD[role])
    .filter(Boolean);

  if (matched.length === 0) return null;

  return DASHBOARD_PRIORITY.find((d) => matched.includes(d)) || matched[0];
}
