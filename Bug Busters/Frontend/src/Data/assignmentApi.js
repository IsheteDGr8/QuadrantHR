// Client for the real backend policy-assignment/progress endpoints
// (backend/main.py's "Policy Assignments" section). These are keyed on
// email (the signed-in user's real identity - see backend/auth.py),
// not the display-name ids Data/store.js's local mock uses.

import { BACKEND_URL, ORG_ID } from "./backendConfig";
import { getAuthHeader } from "./authToken";

export async function assignPolicyToEmails(policyId, emails) {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/policies/${ORG_ID}/${policyId}/assign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authHeader || {}),
    },
    body: JSON.stringify({ user_ids: emails }),
  });

  if (!response.ok) {
    throw new Error(`Failed to assign policy (${response.status})`);
  }

  return response.json();
}

// { assigned: number, signed: number, policies: [{policy_id, policy_name, signed}] }
export async function getUserProgress(email) {
  const authHeader = await getAuthHeader();

  const response = await fetch(
    `${BACKEND_URL}/policies/${ORG_ID}/users/${encodeURIComponent(email)}/progress`,
    { headers: authHeader || undefined }
  );

  if (!response.ok) {
    throw new Error(`Failed to load progress (${response.status})`);
  }

  return response.json();
}

// Rolls a real progress response up into the same {variant, label} shape
// the dashboards already render with Tag - real counts instead of the
// old bundle-based "Signed <date>" / "Pending" / "Not sent" text, since
// a person's real progress spans however many individual policies
// they've actually been assigned, not one bundle.
// Whether every one of the given real policy_ids shows as signed in a
// progress response - used where the UI still shows one bundle/role at
// a time (e.g. PolicyOverall.jsx's per-role Signatures table) rather
// than the person's overall progress.
export function isFullySignedFor(progress, policyIds) {
  if (!progress || policyIds.length === 0) return false;

  const signedIds = new Set(
    progress.policies.filter((p) => p.signed).map((p) => p.policy_id)
  );

  return policyIds.every((id) => signedIds.has(id));
}

export function summarizeProgress(progress) {
  if (!progress || progress.assigned === 0) {
    return { variant: "neutral", label: "Not sent" };
  }

  if (progress.signed === progress.assigned) {
    return { variant: "accent", label: "All signed" };
  }

  return { variant: "amber", label: `${progress.signed}/${progress.assigned} signed` };
}
