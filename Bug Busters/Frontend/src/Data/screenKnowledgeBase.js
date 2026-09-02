// Knowledge base for Buggy's "explain this screen" feature — "what is the
// Dashboard for?", "explain the Policies page", "what does this page do?".
//
// This app has no router (no react-router anywhere) — `id` below is an
// internal screen identifier, not a real URL path. Pages that render
// <MiniChatWidget> pass their current one down as the `currentScreen`
// prop so "what does this page do?"/"where am I?" can resolve without
// the user naming it.
//
// To document a new screen: add an entry here. Nothing in
// MiniChatWidget.jsx or chatWidgetApi.js needs to change — see
// findScreen()/getScreenById() below, which are the only two things that
// read this file.
export const SCREENS = [
  {
    id: "landing",
    name: "Landing page",
    aliases: ["landing", "landing page", "welcome page", "home page"],
    purpose:
      "The first screen anyone sees before signing in — pitches what Policy Guardian does and hands off to sign-in.",
    keyActions: ["Read what the app does", "Click \"Get started\" to sign in"],
  },
  {
    id: "login",
    name: "Sign in page",
    aliases: ["login", "log in", "sign in", "signin page"],
    purpose: "Where you authenticate — real Microsoft sign-in, or a demo account as a fallback.",
    keyActions: [
      "Sign in with your organization Microsoft account",
      "Use a demo account instead (no real Entra account needed)",
    ],
  },
  {
    id: "demo-login",
    name: "Demo sign-in page",
    aliases: ["demo login", "demo sign in", "demo account page"],
    purpose:
      "A fallback sign-in for demos — looks up one of a few seeded demo accounts (HR/Manager/Intern/Engineer) by email, no password.",
    keyActions: ["Pick a demo account", "Type a demo email and continue"],
  },
  {
    id: "hr-home",
    name: "HR Dashboard (Home)",
    aliases: ["hr dashboard", "hr home", "dashboard"],
    purpose:
      "HR's overview — live policy counts, sign-off progress, who hasn't signed yet, and quick links to file an incident report or start onboarding work.",
    keyActions: [
      "See policy signing status across the org",
      "Jump into a specific role's policies",
      "File an incident report",
    ],
  },
  {
    id: "hr-policies",
    name: "Policies page",
    aliases: ["policies page", "policy library", "policies"],
    purpose:
      "Browse and manage every role's policy sections — draft new ones, edit existing ones, or view a role's combined policy.",
    keyActions: [
      "Select a role to see its sections",
      "Generate a new section with AI",
      "Upload an existing policy instead of writing one",
      "Open a section to edit it",
    ],
  },
  {
    id: "hr-teams",
    name: "Teams page",
    aliases: ["teams page", "teams"],
    purpose: "Shows who's on which team and each person's policy sign-off status.",
    keyActions: ["See team rosters", "Check an individual's signing status"],
  },
  {
    id: "hr-tickets",
    name: "Tickets page",
    aliases: ["tickets page", "tickets", "feedback tickets"],
    purpose:
      "Manager feedback about an employee or situation, auto-routed here — review it, add notes, and update its status.",
    keyActions: [
      "Open a ticket to see the full feedback and audit trail",
      "Move a ticket to In Review, Resolved, or Escalated",
      "Add a note to a ticket",
    ],
  },
  {
    id: "settings",
    name: "Settings page",
    aliases: ["settings page", "settings"],
    purpose: "Personal appearance preferences — theme, typeface, and text size.",
    keyActions: ["Switch between light/dark/system theme", "Change typeface or text size"],
  },
  {
    id: "section-editor",
    name: "Section Editor",
    aliases: ["section editor", "policy editor", "edit section"],
    purpose:
      "Edit one policy section's text directly, ask AI about a highlighted passage or have it reworded, and export as PDF/DOCX.",
    keyActions: [
      "Edit the section text",
      "Highlight text, then Ask AI or Reword",
      "View version history",
      "Download as PDF or DOCX",
    ],
  },
  {
    id: "section-generate",
    name: "Generate Policy questionnaire",
    aliases: ["generate policy", "questionnaire", "create section"],
    purpose: "A short questionnaire that AI uses to draft a brand-new policy section from scratch.",
    keyActions: ["Answer the questionnaire", "Generate a first draft"],
  },
  {
    id: "upload-policy-form",
    name: "Upload existing policy",
    aliases: ["upload policy", "upload existing policy", "import policy"],
    purpose:
      "Bring in a policy you already have — .txt/.md are read directly, .pdf/.docx go through the backend to extract the text.",
    keyActions: ["Choose a file to upload", "Review the extracted text before saving"],
  },
  {
    id: "policy-overall",
    name: "Overall / Send Policy page",
    aliases: ["overall page", "send policy", "combined policy"],
    purpose:
      "Preview a role's full combined policy (every section stitched together) and send it out to employees to sign.",
    keyActions: ["Preview the combined policy", "Pick recipients and send it", "View a signed record"],
  },
  {
    id: "incident-report",
    name: "Incident Report Assistant",
    aliases: ["incident report", "incident assistant", "file an incident"],
    purpose:
      "Describe what happened in a chat; it's matched to the relevant policy and a follow-up question, then routed for human review.",
    keyActions: ["Describe an incident", "Answer the follow-up question", "Submit for review"],
  },
  {
    id: "employee-home",
    name: "Your Policies (Employee/Intern home)",
    aliases: ["employee dashboard", "intern dashboard", "your policies", "my policies", "dashboard"],
    purpose:
      "Your own assigned policies — see what needs your signature, your compliance badge per policy, and complete onboarding.",
    keyActions: [
      "Read & sign a pending policy",
      "Complete the Attest/Train/Adhere onboarding flow",
    ],
  },
  {
    id: "employee-materials",
    name: "Training Materials",
    aliases: ["materials", "materials page", "training materials"],
    purpose: "Reference training resources uploaded for onboarding and ongoing policy compliance.",
    keyActions: ["Browse available training materials", "Download a resource"],
  },
  {
    id: "policy-viewer",
    name: "Policy Viewer",
    aliases: ["policy viewer", "sign policy", "read and sign"],
    purpose: "Read an assigned policy and sign it — by typing your name or drawing a signature.",
    keyActions: ["Highlight text to ask AI about it", "Type or draw your signature", "Sign & accept"],
  },
  {
    id: "signed-record",
    name: "Signed Record",
    aliases: ["signed record", "signature record"],
    purpose: "A permanent, read-only record of exactly what one person signed and when.",
    keyActions: ["Review the signed content and signature", "Go back to the signing-status list"],
  },
  {
    id: "manager-home",
    name: "Manager Dashboard",
    aliases: ["manager dashboard", "manager home", "dashboard"],
    purpose: "A manager's view of their own policies plus their team's signing progress.",
    keyActions: ["Sign your own assigned policies", "Check your team's status", "Send a reminder"],
  },
  {
    id: "access-denied",
    name: "Access Denied page",
    aliases: ["access denied"],
    purpose:
      "Shown when you're signed in but your account has no role mapped to a dashboard yet — not an error, just missing role assignment.",
    keyActions: ["Log out and try a different account", "Contact an admin to get a role assigned"],
  },
];

// Case-insensitive substring match against each screen's name + aliases.
// Returns the single best match, or null if nothing looks relevant —
// deliberately conservative (see MiniChatWidget.jsx: "I don't have info
// on that screen yet" beats guessing wrong).
export function findScreen(query) {
  const q = query.toLowerCase();

  return (
    SCREENS.find((s) => [s.name, ...s.aliases].some((a) => q.includes(a.toLowerCase()))) || null
  );
}

export function getScreenById(id) {
  return SCREENS.find((s) => s.id === id) || null;
}
