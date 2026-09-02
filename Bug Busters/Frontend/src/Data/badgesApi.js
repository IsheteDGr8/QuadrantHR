// Client for a per-policy badge endpoint — shown on the Employee/Intern
// home page (EmployeeDashboard.jsx) next to each assigned policy.
//
// Unlike incidentApi.js/signatureApi.js, there is NO real backend contract
// to align this to: grepped "badge" across backend/ on main and every
// unmerged teammate branch (maria-entra-auth, maria-signature-workflow,
// maria-incident-assistant, maria-policy-guardian-backend,
// maria-citation-links, dhruv-main, pranag) — zero hits. The shape below
// is invented, not confirmed, and needs sign-off from whoever owns the
// backend before GET_BADGES_URL is real. Treat the "real" branch here as
// a placeholder to swap in once that contract actually exists.
//
// Badge concept: an at-a-glance compliance/urgency read on one assigned
// policy — not the same thing as assignment.status (signed/pending),
// which is a fact. A badge is a judgment: "on_time" once signed, "overdue"
// once a review-cycle deadline has passed unsigned, "due_soon" as that
// deadline approaches, "new" otherwise.

import { getAuthHeader } from "./authToken";

const USE_MOCKS = true;
const BACKEND_URL = "https://app-ai-policy-backend.azurewebsites.net"; // placeholder, unconfirmed

const DUE_SOON_DAYS = 7;
const REVIEW_CYCLE_DAYS = 30; // shorter placeholder cycle just for badge demo purposes

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function daysBetween(a, b) {
  return (b.getTime() - a.getTime()) / (24 * 60 * 60 * 1000);
}

// variant maps onto Tag.jsx's actual supported variants (accent, accent-2,
// neutral, outline, amber, fill) — there's no separate "warning"/"danger"
// variant in this design system, so overdue reuses accent-2 (the same
// rust/red tone .btn-danger uses) and due_soon reuses amber (the same
// tone PolicyOverall already uses for "Pending").
function computeBadge(assignment) {
  if (assignment.status === "signed") {
    return { badge: "on_time", label: "Signed on time", variant: "accent" };
  }

  const sentAt = assignment.sentAt ? new Date(assignment.sentAt) : new Date();
  const daysSinceSent = daysBetween(sentAt, new Date());
  const daysUntilDue = REVIEW_CYCLE_DAYS - daysSinceSent;

  if (daysUntilDue <= 0) {
    return { badge: "overdue", label: "Overdue", variant: "accent-2" };
  }

  if (daysUntilDue <= DUE_SOON_DAYS) {
    return { badge: "due_soon", label: "Due soon", variant: "amber" };
  }

  return { badge: "new", label: "New", variant: "neutral" };
}

export async function getBadgesForEmployee(employeeId, assignments) {
  if (USE_MOCKS) {
    await delay(300);
    return assignments.map((a) => ({ policy_id: a.id, ...computeBadge(a) }));
  }

  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/api/badges?employee_id=${encodeURIComponent(employeeId)}`, {
    headers: authHeader || undefined,
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return response.json();
}
