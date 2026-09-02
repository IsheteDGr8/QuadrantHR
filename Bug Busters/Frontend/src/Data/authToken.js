import { getDemoUser } from "./demoAuth";

// Returns the header object every authenticated backend call needs to
// send, or null if nobody's signed in. backend/auth.py trusts these
// headers as-is - no token, no signature (see that file's docstring for
// why - this is a demo-only login, not real auth).
//
// Kept as a headers OBJECT (not a single "Authorization" string like the
// old MSAL-based version) since three separate headers are needed now.
// Callers spread it directly: `...(getAuthHeader() ?? {})`.
export function getAuthHeader() {
  const user = getDemoUser();
  if (!user) return null;

  return {
    "X-Demo-Email": user.email,
    "X-Demo-Role": user.role,
    "X-Demo-Name": user.display_name || user.email,
  };
}
