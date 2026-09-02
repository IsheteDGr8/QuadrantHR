import { useEffect, useState } from "react";
import {
  sendRoleToEmployees,
  saveSection,
  getMockUsersByRole,
  getAssignmentsForEmployee,
  roleLabel,
  getMockManager,
} from "../Data/store";
import { saveSectionToBackend } from "../Data/policyExport";
import { assignPolicyToEmails, getUserProgress, isFullySignedFor } from "../Data/assignmentApi";
import { formatShortDate } from "../utils/format";
import PolicyContent from "../components/policy/PolicyContent";
import Button from "../components/ui/Button";
import Tag from "../components/ui/Tag";

// Shows every section for a role stitched into one document.
// HR can select specific people and send the policy to them, and see
// who has already signed (the per-policy view of signatures — the
// per-employee view lives on the HR home / Teams tables).

function PolicyOverall({ role, sections, onViewRecord, onEditSection, onAddSection, onBack }) {
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const [selectedRecipients, setSelectedRecipients] = useState([]);
  const [realSignedByPersonId, setRealSignedByPersonId] = useState({});

  const roleSections = sections.filter((s) => s.role === role);
  const recipients = getMockUsersByRole(role);
  const signatures = recipients
    .map((person) => ({
      person,
      assignment: getAssignmentsForEmployee(person.id).find((a) => a.role === role),
    }))
    .filter((row) => row.assignment);

  // Overlays real signed-status on top of the local assignment record
  // above (which still supplies the sent-date and click-to-view-record
  // behavior). Falls back to the local status for pre-existing
  // assignments sent before real policy_ids existed.
  useEffect(() => {
    const policyIds = roleSections.map((s) => s.backendPolicyId).filter(Boolean);
    if (policyIds.length === 0 || signatures.length === 0) return;

    let cancelled = false;

    Promise.all(
      signatures.map(async ({ person }) => {
        if (!person.email) return [person.id, null];
        try {
          const progress = await getUserProgress(person.email);
          return [person.id, isFullySignedFor(progress, policyIds)];
        } catch {
          return [person.id, null];
        }
      })
    ).then((entries) => {
      if (!cancelled) setRealSignedByPersonId(Object.fromEntries(entries));
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, sent]);

  function toggleRecipient(userId) {
    setSelectedRecipients((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : [...prev, userId]
    );

    setSent(false);
  }

  function selectAll() {
    setSelectedRecipients(recipients.map((person) => person.id));
    setSent(false);
  }

  function clearAll() {
    setSelectedRecipients([]);
    setSent(false);
  }

  async function handleSend() {
    setSending(true);
    setSendError("");

    try {
      // Every section needs a real backend policy_id before it can be
      // assigned for real - auto-save any that haven't been saved yet
      // (e.g. never exported/downloaded), same save path exportSection
      // uses, and remember the id locally so this only happens once per
      // section.
      const savedSections = await Promise.all(
        roleSections.map(async (section) => {
          if (section.backendPolicyId) return section;

          const saved = await saveSectionToBackend(section);
          return saveSection({ ...section, backendPolicyId: saved.id });
        })
      );

      const recipientEmails = recipients
        .filter((person) => selectedRecipients.includes(person.id))
        .map((person) => person.email)
        .filter(Boolean);

      await Promise.all(
        savedSections.map((section) =>
          assignPolicyToEmails(section.backendPolicyId, recipientEmails)
        )
      );

      // Local bundle bookkeeping (drives the KPI tiles/activity feed) -
      // unchanged, still runs alongside the real assignment above.
      sendRoleToEmployees(role, selectedRecipients);
      setSent(true);
    } catch (err) {
      setSendError(err.message || "Failed to send policy. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="policy-editor">
      {onBack && (
        <Button variant="secondary" size="sm" onClick={onBack} style={{ marginBottom: 8 }}>
          ← Back to Policies
        </Button>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
        <div>
          <h1>{roleLabel(role)} — Overall Policy</h1>

          <p className="editor-hint">
            All sections for the {roleLabel(role)} role, combined into one
            document.
          </p>
        </div>

        {onAddSection && (
          <Button variant="secondary" size="sm" onClick={() => onAddSection(role)}>
            + Add Section
          </Button>
        )}
      </div>

      {roleSections.length === 0 ? (
        <p className="sidebar-empty">
          No sections yet. Add one from the Home page.
        </p>
      ) : (
        <div className="overall-sections">
          {roleSections.map((section) => (
            <div className="overall-section" key={section.id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h2>{section.title}</h2>
                {onEditSection && (
                  <button className="link-button" onClick={() => onEditSection(section)}>
                    Edit
                  </button>
                )}
              </div>

              <PolicyContent content={section.content} />
            </div>
          ))}
        </div>
      )}

      {roleSections.length > 0 && (
        <div className="card panel recipient-panel">
          <h2>Send Policy</h2>

          <p className="editor-hint">
            Select who should receive this policy.
          </p>

          {recipients.length === 0 ? (
            <p className="sidebar-empty">
              No users currently have the {roleLabel(role)} role.
            </p>
          ) : (
            <>
              <div className="recipient-actions">
                <Button variant="secondary" size="sm" onClick={selectAll}>
                  Select All
                </Button>

                <Button variant="secondary" size="sm" onClick={clearAll}>
                  Clear
                </Button>
              </div>

              <div className="recipient-list">
                {recipients.map((person) => {
                  const manager = person.managerId
                    ? getMockManager(person.managerId)
                    : null;

                  return (
                    <label
                      key={person.id}
                      className="recipient-row"
                    >
                      <input
                        type="checkbox"
                        checked={selectedRecipients.includes(person.id)}
                        onChange={() => toggleRecipient(person.id)}
                      />

                      <span className="recipient-name">
                        {person.name}
                      </span>

                      {manager && (
                        <span className="recipient-team">
                          {manager.name}'s Team
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>

              <p>
                <strong>{selectedRecipients.length}</strong>{" "}
                {selectedRecipients.length === 1
                  ? "person"
                  : "people"}{" "}
                selected
              </p>

              <Button
                variant="primary"
                onClick={handleSend}
                disabled={selectedRecipients.length === 0 || sending}
              >
                {sending ? "Sending…" : "Send Policy"}
              </Button>
            </>
          )}

          {sendError && <p className="sign-error">{sendError}</p>}

          {sent && (
            <p className="sent-confirmation">
              Policy sent to {selectedRecipients.length}{" "}
              {selectedRecipients.length === 1
                ? "person"
                : "people"}.
            </p>
          )}
        </div>
      )}

      {signatures.length > 0 && (
        <div className="card panel recipient-panel" style={{ marginTop: 24 }}>
          <h2>Signatures</h2>
          <p className="editor-hint">
            Everyone this policy has been sent to, and whether they've signed it.
          </p>

          <table className="table">
            <thead>
              <tr>
                <th>Person</th>
                <th style={{ textAlign: "right" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {signatures.map(({ person, assignment }) => {
                const isSigned = realSignedByPersonId[person.id] ?? (assignment.status === "signed");
                return (
                  <tr
                    key={person.id}
                    onClick={isSigned ? () => onViewRecord?.(assignment, person.name) : undefined}
                    style={{ cursor: isSigned ? "pointer" : "default" }}
                  >
                    <td data-label="Person" style={{ fontWeight: 600 }}>{person.name}</td>
                    <td data-label="Status" style={{ textAlign: "right" }}>
                      {isSigned ? (
                        <Tag variant="accent">Signed {formatShortDate(assignment.signedAt)}</Tag>
                      ) : (
                        <Tag variant="amber">Pending</Tag>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default PolicyOverall;