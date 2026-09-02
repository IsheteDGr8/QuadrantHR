import { useEffect, useState } from "react";
import PolicyViewer from "./PolicyViewer";
import Settings from "./Settings";
import TopNav from "../components/ui/TopNav";
import Button from "../components/ui/Button";
import Tag from "../components/ui/Tag";
import { Field, Select } from "../components/ui/FormControls";
import ManagerCoverageDonut from "../components/ManagerCoverageDonut";
import MiniChatWidget from "../components/chat/MiniChatWidget";
import {
  getAssignmentsForEmployee,
  getAssignment,
  getMockTeam,
  getMockManager,
  getAllRoles,
  getSectionsByRole,
  sendRoleToEmployees,
  roleLabel,
  saveSection,
} from "../Data/store";
import { saveSectionToBackend } from "../Data/policyExport";
import { getUserProgress, isFullySignedFor, assignPolicyToEmails } from "../Data/assignmentApi";
import { createTicket } from "../Data/ticketsApi";
import { greeting, formattedToday, formatShortDate } from "../utils/format";

const NAV_TABS = [
  { key: "home", label: "Home" },
  { key: "settings", label: "Settings" },
];

function ManagerDashboard({ user, onLogout }) {
  const [view, setView] = useState("home"); // "home" | "settings"
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignRole, setAssignRole] = useState("");
  const [assignRecipients, setAssignRecipients] = useState([]);
  const [assignSent, setAssignSent] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState("");
  const [reminderNote, setReminderNote] = useState("");
  const [sendingReminder, setSendingReminder] = useState(false);
  const [reminderError, setReminderError] = useState("");
  // Signing a policy mutates the store (localStorage) directly, so this
  // just forces a re-render to pick the change back up.
  const [, forceRefresh] = useState(0);

  // `user` is now a real Entra display name/username (see App.jsx), not one
  // of the fake "manager1"/"manager2" ids the mock org chart (MOCK_USERS in
  // Data/store.js) is keyed on. All three lookups below will come back
  // empty for a real account — no crash, but manager name/team/assignments
  // will just show blank until the backend supplies real org-chart data.
  const manager = getMockManager(user);
  const myAssignments = getAssignmentsForEmployee(user);
  const teamMembers = getMockTeam(user).map((member) => ({
    ...member,
    assignments: getAssignmentsForEmployee(member.id),
  }));

  const [progressByMemberId, setProgressByMemberId] = useState({});

  // Real, cross-user signed status - overlaid per-assignment below
  // (checking whether every real policy_id in that assignment's bundle
  // is signed), same pattern as HRDashboard.jsx.
  useEffect(() => {
    let cancelled = false;

    Promise.all(
      teamMembers.map(async (member) => {
        if (!member.email) return [member.id, null];
        try {
          return [member.id, await getUserProgress(member.email)];
        } catch {
          return [member.id, null];
        }
      })
    ).then((entries) => {
      if (!cancelled) setProgressByMemberId(Object.fromEntries(entries));
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  function realIsSigned(member, assignment) {
    const progress = progressByMemberId[member.id];
    const policyIds = assignment.parts.map((p) => p.backendPolicyId).filter(Boolean);

    if (!progress || policyIds.length === 0) return assignment.status === "signed";

    return isFullySignedFor(progress, policyIds);
  }

  // Only offer policies HR has actually built at least one section for.
  const assignableRoles = getAllRoles().filter((r) => getSectionsByRole(r.id).length > 0);

  function refresh() {
    forceRefresh((n) => n + 1);
  }

  function handleSigned() {
    refresh();
    setSelectedAssignment((prev) => (prev ? getAssignment(prev.id) : prev));
  }

  const rows = teamMembers.flatMap((member) =>
    member.assignments.length === 0
      ? [{ member, policyLabel: "—", status: { variant: "neutral", label: "Not sent" } }]
      : member.assignments.map((a) => {
          const signed = realIsSigned(member, a);
          return {
            member,
            policyLabel: `${roleLabel(a.role)} Policy`,
            status: signed
              ? { variant: "accent", label: `Signed ${formatShortDate(a.signedAt)}` }
              : { variant: "amber", label: "Pending" },
          };
        })
  );

  const pendingMembers = teamMembers.filter(
    (m) => m.assignments.length > 0 && m.assignments.some((a) => !realIsSigned(m, a))
  );

  const donutCounts = { signed: 0, pending: 0, notSent: 0 };
  teamMembers.forEach((m) => {
    if (m.assignments.length === 0) donutCounts.notSent++;
    else if (m.assignments.some((a) => realIsSigned(m, a))) donutCounts.signed++;
    else donutCounts.pending++;
  });

  async function handleSendReminder() {
    if (sendingReminder) return;

    setSendingReminder(true);
    setReminderError("");

    try {
      await createTicket({
        type: "reminder",
        role: null,
        title: `Reminder: ${pendingMembers.length} pending signature${pendingMembers.length === 1 ? "" : "s"}`,
        body: `${manager?.name || "A manager"} requested a nudge for: ${pendingMembers
          .map((m) => m.name)
          .join(", ")}.`,
      });

      setReminderNote(
        `Reminder sent to ${pendingMembers.length} report${pendingMembers.length === 1 ? "" : "s"} with a pending signature.`
      );
      setTimeout(() => setReminderNote(""), 3000);
    } catch (err) {
      setReminderError(err.message || "Failed to send reminder. Please try again.");
    } finally {
      setSendingReminder(false);
    }
  }

  function toggleRecipient(id) {
    setAssignRecipients((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    setAssignSent(false);
  }

  async function handleAssignPolicy(e) {
    e.preventDefault();
    if (!assignRole || assignRecipients.length === 0 || assigning) return;

    setAssigning(true);
    setAssignError("");

    try {
      const roleSections = getSectionsByRole(assignRole);

      const savedSections = await Promise.all(
        roleSections.map(async (section) => {
          if (section.backendPolicyId) return section;
          const saved = await saveSectionToBackend(section);
          return saveSection({ ...section, backendPolicyId: saved.id });
        })
      );

      const recipientEmails = teamMembers
        .filter((m) => assignRecipients.includes(m.id))
        .map((m) => m.email)
        .filter(Boolean);

      await Promise.all(
        savedSections.map((section) =>
          assignPolicyToEmails(section.backendPolicyId, recipientEmails)
        )
      );

      sendRoleToEmployees(assignRole, assignRecipients);
      setAssignSent(true);
      setAssignRecipients([]);
      refresh();
    } catch (err) {
      setAssignError(err.message || "Failed to assign policy. Please try again.");
    } finally {
      setAssigning(false);
    }
  }

  return (
    <div>
      <TopNav tabs={NAV_TABS} activeTab={view} onTabChange={setView} userName={manager?.name || user} userRole="Manager" onLogout={onLogout} />

      {view === "settings" ? (
        <div className="content">
          <Settings />
        </div>
      ) : selectedAssignment ? (
        <div className="content">
          <Button variant="secondary" size="sm" onClick={() => setSelectedAssignment(null)} style={{ marginBottom: 16 }}>
            ← Back
          </Button>
          <PolicyViewer assignment={selectedAssignment} onSigned={handleSigned} allowFeedback />
        </div>
      ) : (
        <div className="content">
          <div className="page-kicker">{manager?.name ? `${manager.name}'s Team` : "Your Team"}</div>
          <div className="page-greeting-row">
            <h1>{greeting()}, {manager?.name || user}</h1>
            <span className="page-greeting-date">{formattedToday()}</span>
          </div>
          <p className="page-lede">
            {teamMembers.length} report{teamMembers.length === 1 ? "" : "s"}. You can nudge and send, but not edit policy text.
          </p>

          {myAssignments.length > 0 && (
            <div style={{ marginBottom: 40 }}>
              <h3 style={{ margin: "0 0 4px" }}>Your policies</h3>
              <p style={{ margin: "0 0 16px", color: "var(--color-text-muted)", fontSize: 14 }}>
                Policies HR has assigned to you directly.
              </p>
              <table className="table">
                <thead>
                  <tr>
                    <th>Policy</th>
                    <th>Sent</th>
                    <th style={{ textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {myAssignments.map((a) => (
                    <tr key={a.id}>
                      <td data-label="Policy" style={{ fontWeight: 600 }}>{roleLabel(a.role)}</td>
                      <td data-label="Sent">{formatShortDate(a.sentAt)}</td>
                      <td data-label="Action" style={{ textAlign: "right" }}>
                        {a.status === "signed" ? (
                          <Button variant="secondary" size="sm" onClick={() => setSelectedAssignment(a)}>
                            View
                          </Button>
                        ) : (
                          <Button variant="primary" size="sm" onClick={() => setSelectedAssignment(a)}>
                            Read &amp; sign
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ display: "flex", gap: 56, alignItems: "flex-start", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 480px" }}>
              <h3 style={{ margin: "0 0 4px" }}>Team status</h3>
              {rows.length === 0 ? (
                <p className="sidebar-empty">No team members yet.</p>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Report</th>
                      <th>Role</th>
                      <th>Policy</th>
                      <th style={{ textAlign: "right" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={`${row.member.id}-${i}`}>
                        <td data-label="Report" style={{ fontWeight: 600 }}>{row.member.name}</td>
                        <td data-label="Role">{roleLabel(row.member.role)}</td>
                        <td data-label="Policy">{row.policyLabel}</td>
                        <td data-label="Status" style={{ textAlign: "right" }}>
                          <Tag variant={row.status.variant}>{row.status.label}</Tag>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <Button
                    variant="primary"
                    onClick={handleSendReminder}
                    disabled={pendingMembers.length === 0 || sendingReminder}
                    title={pendingMembers.length === 0 ? "No pending signatures on your team" : undefined}
                  >
                    {sendingReminder ? "Sending..." : "Send reminder"}
                  </Button>
                  <Button variant="secondary" onClick={() => setAssignOpen((v) => !v)}>
                    Assign a policy
                  </Button>
                  {reminderNote && <span className="sent-confirmation">{reminderNote}</span>}
                  {reminderError && (
                    <span style={{ color: "var(--color-danger, #c0392b)" }}>{reminderError}</span>
                  )}
                </div>

                {assignOpen && (
                  <div className="card panel" style={{ maxWidth: 420 }}>
                    <h4 style={{ margin: 0 }}>Assign a policy</h4>

                    {assignableRoles.length === 0 || teamMembers.length === 0 ? (
                      <p className="sidebar-empty">
                        {teamMembers.length === 0
                          ? "You have no reports to assign a policy to."
                          : "HR hasn't built any policies yet."}
                      </p>
                    ) : (
                      <form onSubmit={handleAssignPolicy} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                        <Field label="Policy">
                          <Select value={assignRole} onChange={(e) => { setAssignRole(e.target.value); setAssignSent(false); }} required>
                            <option value="" disabled>Select a policy</option>
                            {assignableRoles.map((r) => (
                              <option key={r.id} value={r.id}>{r.label}</option>
                            ))}
                          </Select>
                        </Field>

                        <Field label="Recipients">
                          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                            {teamMembers.map((m) => (
                              <label key={m.id} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
                                <input
                                  type="checkbox"
                                  checked={assignRecipients.includes(m.id)}
                                  onChange={() => toggleRecipient(m.id)}
                                />
                                {m.name}
                              </label>
                            ))}
                          </div>
                        </Field>

                        <Button
                          variant="primary"
                          type="submit"
                          disabled={!assignRole || assignRecipients.length === 0 || assigning}
                          style={{ alignSelf: "flex-start" }}
                        >
                          {assigning ? "Sending…" : "Send policy"}
                        </Button>

                        {assignError && <p className="sign-error">{assignError}</p>}
                        {assignSent && <p className="sent-confirmation">Policy assigned.</p>}
                      </form>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div style={{ width: 250 }}>
              <h4 style={{ margin: "0 0 14px" }}>Signature coverage</h4>
              <ManagerCoverageDonut {...donutCounts} />
            </div>
          </div>
        </div>
      )}

      <MiniChatWidget
        title="Buggy"
        placeholder="Ask a question..."
        currentScreen={view === "settings" ? "settings" : selectedAssignment ? "policy-viewer" : "manager-home"}
        navigateTo={(screenId) => {
          const key = screenId.replace(/^manager-/, "");
          const exists = NAV_TABS.some((t) => t.key === key);
          if (exists) setView(key);
          return exists;
        }}
      />
    </div>
  );
}

export default ManagerDashboard;
