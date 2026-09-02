// Demo login session. Replaces the real Entra/MSAL flow entirely (see
// backend/auth.py - the backend no longer validates real tokens at all,
// only these three headers) and Data/authToken.js reads this to build
// them on every backend call.
//
// sessionStorage, not localStorage: matches the previous MSAL cache
// behavior (signed out on tab close, no cross-tab SSO) rather than
// silently introducing a longer-lived session than the app had before.

import { BACKEND_URL } from "./backendConfig";

const SESSION_KEY = "demoUser";

export function getDemoUser() {
  const stored = sessionStorage.getItem(SESSION_KEY);
  return stored ? JSON.parse(stored) : null;
}

export async function demoLogin(email) {
  const response = await fetch(`${BACKEND_URL}/demo-login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || "No demo user found with that email.");
  }

  const user = await response.json();
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
  return user;
}

export function demoLogout() {
  sessionStorage.removeItem(SESSION_KEY);
}
