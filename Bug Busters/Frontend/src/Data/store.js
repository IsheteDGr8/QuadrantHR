// Lightweight stand-in for a real backend. Everything is persisted to
// localStorage so HR, Manager, and Employee views (in the same browser)
// can share data. Swap these functions for real API calls once a backend
// exists.

const SECTIONS_KEY = "app_sections";
const ASSIGNMENTS_KEY = "app_assignments";

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

// ----- Roles -----

// "employee" was a generic placeholder from before real roles existed -
// removed since every real signed-in person is HR/Manager/Intern/
// Engineer (Intern is the one that maps to the "employee" dashboard
// key in roleConfig.js, but that's a dashboard-routing detail, not a
// role anyone actually has).
export const BUILT_IN_ROLES = [
  { id: "manager", label: "Manager" },
  { id: "hr", label: "HR" },
  { id: "intern", label: "Intern" },
  { id: "engineer", label: "Engineer" },
];

// ----- Mock users / managers / teams -----

// id is each person's real display_name (see backend/demo_login_db.py's
// SEED_USERS) - dashboards look someone up by comparing this to the
// signed-in identity (see ManagerDashboard.jsx/EmployeeDashboard.jsx),
// so it has to match exactly, not just be a friendly label.
//
// email is their real demo-login identity - the backend's actual
// user_id (see backend/auth.py: object_id = the signed-in email, not
// the display name). Needed for real assign/sign/progress calls, which
// are keyed on email, not on this file's local display-name ids.
//
// Team assignments (who reports to which manager) weren't specified
// alongside the role list, so this is an even split by list order, not
// a real org chart - update if the actual reporting structure differs.
export const MOCK_USERS = [
  { id: "Areef Shaik", name: "Areef", role: "manager", email: "areef.shaik@quadranttechnologies.com" },
  { id: "Sai Saketh", name: "Saketh", role: "manager", email: "sai.saketh@quadranttechnologies.com" },

  { id: "Khusum R", name: "Khusum", role: "intern", managerId: "Areef Shaik", email: "i-khusum.r@quadranttechnologies.com" },
  { id: "Maria Zia", name: "Maria", role: "intern", managerId: "Areef Shaik", email: "i-maria.zia@quadranttechnologies.com" },
  { id: "Dhruv K", name: "Dhruv", role: "engineer", managerId: "Areef Shaik", email: "i-dhruv.k@quadranttechnologies.com" },

  { id: "Pranay A", name: "Pranay", role: "intern", managerId: "Sai Saketh", email: "i-pranay.a@quadranttechnologies.com" },
  { id: "Chaithra Allapuraju", name: "Chaithra", role: "intern", managerId: "Sai Saketh", email: "i-chaithra.allapuraju@quadranttechnologies.com" },
  { id: "Abhishek S", name: "Abhishek", role: "engineer", managerId: "Sai Saketh", email: "i-abhishek.s@quadranttechnologies.com" },
];

export function getMockUsersByRole(role) {
  return MOCK_USERS.filter((user) => user.role === role);
}

export function getMockTeam(managerId) {
  return MOCK_USERS.filter(
    (user) => user.managerId === managerId
  );
}

export function getMockManager(managerId) {
  return MOCK_USERS.find(
    (user) => user.id === managerId
  );
}

// Which real logins can receive a given role's policy.
//
// For now, the demo has the basic employee login plus the mock users
// above. This can be replaced with real backend users later.
const MOCK_USERS_BY_ROLE = {
  employee: ["emp"],
  intern: ["Khusum R", "Maria Zia", "Pranay A", "Chaithra Allapuraju"],
  engineer: ["Dhruv K", "Abhishek S"],
  manager: ["Areef Shaik", "Sai Saketh"],
};

export function getMockUsersForRole(role) {
  return MOCK_USERS_BY_ROLE[role] || [];
}

const EXTRA_ROLES_KEY = "app_extra_roles";

// Custom roles someone typed in via "+ New role".
export function getExtraRoles() {
  return read(EXTRA_ROLES_KEY, []);
}

export function addRole(label) {
  const trimmed = label.trim();
  const id = trimmed.toLowerCase().replace(/\s+/g, "_");

  if (!id) return null;

  const alreadyBuiltIn = BUILT_IN_ROLES.find((r) => r.id === id);
  const extra = getExtraRoles();

  if (!alreadyBuiltIn && !extra.find((r) => r.id === id)) {
    extra.push({ id, label: trimmed });
    write(EXTRA_ROLES_KEY, extra);
  }

  return id;
}

export function roleLabel(role) {
  if (!role) return "Unknown";

  const known = BUILT_IN_ROLES.find((r) => r.id === role);
  if (known) return known.label;

  const extra = getExtraRoles().find((r) => r.id === role);
  if (extra) return extra.label;

  return role.charAt(0).toUpperCase() + role.slice(1);
}

// Built-in + custom roles only - no longer-valid roles that only exist
// because an old section happens to reference them (see getAllRoles
// below for that). Use this wherever the choice is "start something
// new" (e.g. the New policy section / Upload a policy dropdowns) - a
// removed role like the old "employee" shouldn't be selectable again
// just because a section was tagged with it before it was removed.
export function getSelectableRoles() {
  const map = new Map();

  BUILT_IN_ROLES.forEach((r) => map.set(r.id, r.label));
  getExtraRoles().forEach((r) => map.set(r.id, r.label));

  return Array.from(map.entries()).map(([id, label]) => ({
    id,
    label,
  }));
}

// Every role that's either selectable (see above) or already used on an
// existing section, even if it's since been removed as a selectable
// role - so existing content tagged with it stays visible/manageable
// (e.g. ManagerDashboard's "assign an existing policy" list, PolicyLibrary's
// role cards) instead of silently disappearing.
export function getAllRoles() {
  const used = new Set(getSections().map((s) => s.role));
  const map = new Map(getSelectableRoles().map((r) => [r.id, r.label]));

  used.forEach((id) => {
    if (!map.has(id)) {
      map.set(id, roleLabel(id));
    }
  });

  return Array.from(map.entries()).map(([id, label]) => ({
    id,
    label,
  }));
}

// ----- Sections -----
// A section is one part of a policy.

export function getSections() {
  return read(SECTIONS_KEY, []);
}

export function getSectionsByRole(role) {
  return getSections().filter((s) => s.role === role);
}

export function getSection(id) {
  return getSections().find((s) => s.id === id) || null;
}

// Saving over an existing section snapshots the previous version into
// history when the content changes.
export function saveSection(section) {
  const sections = getSections();
  const index = sections.findIndex((s) => s.id === section.id);

  // New section
  if (index === -1) {
    const newSection = {
      ...section,
      history: section.history || [],
    };

    sections.push(newSection);
    write(SECTIONS_KEY, sections);

    return newSection;
  }

  // Existing section
  const previous = sections[index];
  const history = previous.history || [];
  const contentChanged = previous.content !== section.content;

  if (contentChanged) {
    history.push({
      content: previous.content,
      tone: previous.tone,
      updatedAt: previous.updatedAt,
    });
  }

  const updated = {
    ...section,
    history,
    version: contentChanged ? (previous.version || 1) + 1 : previous.version || 1,
  };

  sections[index] = updated;
  write(SECTIONS_KEY, sections);

  return updated;
}

export function createSection({
  role,
  sectionType,
  title,
  content,
  tone,
  answers,
}) {
  const section = {
    id: `section_${Date.now()}`,
    role,
    sectionType,
    title,
    content,
    tone: tone || "Professional",
    answers: answers || {},
    history: [],
    version: 1,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  return saveSection(section);
}

// Revert a section to a previous version.
export function restoreSectionVersion(sectionId, historyIndex) {
  const section = getSection(sectionId);

  if (
    !section ||
    !section.history ||
    !section.history[historyIndex]
  ) {
    return null;
  }

  const target = section.history[historyIndex];

  const updated = {
    ...section,
    content: target.content,
    tone: target.tone,
    updatedAt: new Date().toISOString(),
  };

  return saveSection(updated);
}

export function deleteSection(id) {
  write(
    SECTIONS_KEY,
    getSections().filter((s) => s.id !== id)
  );
}

// ----- Assignments -----
// A role's completed policy sent to an employee/manager/etc.

export function getAssignments() {
  return read(ASSIGNMENTS_KEY, []).filter(
    (a) => a && a.role && Array.isArray(a.parts)
  );
}

export function getAssignmentsForEmployee(employeeId) {
  return getAssignments().filter(
    (a) => a.employeeId === employeeId
  );
}

export function getAssignment(id) {
  return getAssignments().find((a) => a.id === id) || null;
}

// Snapshots the role's current sections (content + version, as of right
// now) into an assignment. Already-signed assignments are left alone —
// a signature is a permanent record of what someone agreed to, so
// re-sending a role's policy must not silently erase it. Send a fresh
// version to someone who needs to re-sign by having them sign again
// through the normal flow once their status is no longer "signed".
export function sendRoleToEmployees(role, employeeIds) {
  const sections = getSectionsByRole(role);

  const parts = sections.map((s) => ({
    sectionId: s.id,
    title: s.title,
    content: s.content,
    version: s.version || 1,
    // Real backend policy_id, if this section has been saved (see
    // Data/assignmentApi.js - this is what real per-policy assign/sign
    // actually key on, not sectionId which is purely local).
    backendPolicyId: s.backendPolicyId || null,
  }));

  const assignments = getAssignments();

  employeeIds.forEach((employeeId) => {
    const existing = assignments.find(
      (a) =>
        a.role === role &&
        a.employeeId === employeeId
    );

    if (existing && existing.status === "signed") {
      return;
    }

    if (existing) {
      existing.parts = parts;
      existing.sentAt = new Date().toISOString();
      existing.status = "pending";
      existing.signedAt = null;
    } else {
      assignments.push({
        id: `assign_${role}_${employeeId}`,
        role,
        employeeId,
        parts,
        status: "pending",
        sentAt: new Date().toISOString(),
        signedAt: null,
      });
    }
  });

  write(ASSIGNMENTS_KEY, assignments);

  return parts;
}

// ----- Expiration / review cycle -----

const REVIEW_CYCLE_DAYS = 365;

export function getExpirationInfo(section) {
  const created = new Date(section.createdAt).getTime();
  const expires =
    created +
    REVIEW_CYCLE_DAYS * 24 * 60 * 60 * 1000;

  const now = Date.now();

  const totalMs = expires - created;
  const elapsedMs = now - created;

  const percentElapsed = Math.min(
    100,
    Math.max(0, (elapsedMs / totalMs) * 100)
  );

  const daysRemaining = Math.ceil(
    (expires - now) / (24 * 60 * 60 * 1000)
  );

  let status = "ok";

  if (daysRemaining <= 0) {
    status = "overdue";
  } else if (daysRemaining <= 30) {
    status = "soon";
  }

  return {
    expiresAt: new Date(expires).toISOString(),
    percentElapsed,
    daysRemaining,
    status,
  };
}

// ----- Signature stats -----

export function getAssignmentStatsForRole(role) {
  const assignments = getAssignments().filter(
    (a) => a.role === role
  );

  const total = assignments.length;

  const signed = assignments.filter(
    (a) => a.status === "signed"
  ).length;

  return {
    signed,
    total,
  };
}

// ----- Appearance preferences -----
// Per-person, not per-company — see Settings.

const PREFS_KEY = "app_prefs";

export const DEFAULT_PREFS = { theme: "light", typeface: "sans", textSize: "md" };

export function getPrefs() {
  return { ...DEFAULT_PREFS, ...read(PREFS_KEY, {}) };
}

export function savePrefs(prefs) {
  write(PREFS_KEY, prefs);
  return prefs;
}

// Tickets (manager feedback on a policy, signature reminders,
// policy_updated log entries) now live on the real backend — see
// Data/ticketsApi.js (backend/main.py's "Tickets" section /
// feedback_repository.py, #11). No longer mocked here.

// signature is optional — { mode: "type" | "draw", drawingDataUrl } — so
// existing callers that only ever passed a typed name still work.
export function signAssignment(assignmentId, signedBy, signature = null) {
  const assignments = getAssignments();

  const assignment = assignments.find(
    (a) => a.id === assignmentId
  );

  if (assignment) {
    assignment.status = "signed";
    assignment.signedAt = new Date().toISOString();
    assignment.signedBy = signedBy;
    assignment.signature = signature;

    write(ASSIGNMENTS_KEY, assignments);
  }

  return assignment;
}

// ----- Attest/Train/Adhere onboarding -----
// A one-time compliance ritual, separate from signing individual policies
// (see signAssignment above) — per employee, not per policy.

const ONBOARDING_KEY = "app_onboarding";

export function isOnboardingComplete(employeeId) {
  const completed = read(ONBOARDING_KEY, []);
  return completed.some((o) => o.employeeId === employeeId);
}

export function completeOnboarding(employeeId) {
  const completed = read(ONBOARDING_KEY, []);

  if (completed.some((o) => o.employeeId === employeeId)) return;

  completed.push({ employeeId, completedAt: new Date().toISOString() });
  write(ONBOARDING_KEY, completed);
}