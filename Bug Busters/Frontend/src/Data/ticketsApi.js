// Client for the real ticketing backend (backend/main.py's "Tickets"
// section, backed by feedback_repository.py). Replaces Data/store.js's
// old localStorage-backed createTicket/getTickets/resolveTicket mock —
// same three operations, same field shape, just a real POST/GET/PATCH
// now that #11's backend exists. Any signed-in role can create a
// ticket; listing and resolving are HR-only to match the real backend's
// require_role("HR") on those two routes.

import { BACKEND_URL, ORG_ID } from "./backendConfig";
import { getAuthHeader } from "./authToken";

export async function createTicket({ type, role, title, body }) {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/tickets/${ORG_ID}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authHeader || {}),
    },
    body: JSON.stringify({ type, role: role || null, title, body }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create ticket (${response.status})`);
  }

  return response.json();
}

export async function listTickets() {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/tickets/${ORG_ID}`, {
    headers: authHeader || undefined,
  });

  if (!response.ok) {
    throw new Error(`Failed to load tickets (${response.status})`);
  }

  return response.json();
}

export async function resolveTicket(id) {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/tickets/${ORG_ID}/${id}/resolve`, {
    method: "PATCH",
    headers: authHeader || undefined,
  });

  if (!response.ok) {
    throw new Error(`Failed to resolve ticket (${response.status})`);
  }

  return response.json();
}
