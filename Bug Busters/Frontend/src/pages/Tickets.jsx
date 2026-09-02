import { useEffect, useState } from "react";
import { rewordText } from "../Data/aiMock";
import { Input } from "../components/ui/FormControls";
import Button from "../components/ui/Button";
import Tag from "../components/ui/Tag";
import LoadingDots from "../components/ui/LoadingDots";
import { listTickets, createTicket, resolveTicket } from "../Data/ticketsApi";
import {
  getSectionsByRole,
  saveSection,
  getAssignments,
  sendRoleToEmployees,
  roleLabel,
} from "../Data/store";
import { formatShortDate } from "../utils/format";

// Manager feedback lands here as a ticket (backend/main.py's "Tickets"
// section / feedback_repository.py, #11). HR picks which section it
// applies to, and "Apply with AI & resend" reuses the real
// /refine-policy call (via aiMock's rewordText) to regenerate that
// section from the feedback, saves it, and re-sends the role's policy
// to everyone it was previously assigned to. A "policy_updated" ticket
// is logged afterward, standing in for a real email notification.

function FeedbackTicketCard({ ticket, onResolved }) {
  const sections = getSectionsByRole(ticket.role);
  const [sectionTitle, setSectionTitle] = useState(sections[0]?.title || "");
  const [applying, setApplying] = useState(false);

  async function handleApply() {
    if (applying) return;
    const query = sectionTitle.trim().toLowerCase();
    const section = sections.find((s) => s.title.trim().toLowerCase() === query);
    if (!section) {
      alert(`No section titled "${sectionTitle}" found for this role.`);
      return;
    }

    setApplying(true);
    try {
      const revised = await rewordText(ticket.body, section.content);
      saveSection({ ...section, content: revised });

      const recipientIds = getAssignments()
        .filter((a) => a.role === ticket.role)
        .map((a) => a.employeeId);

      if (recipientIds.length > 0) {
        sendRoleToEmployees(ticket.role, recipientIds);
      }

      await createTicket({
        type: "policy_updated",
        role: ticket.role,
        title: `${roleLabel(ticket.role)} policy updated from feedback`,
        body: `"${section.title}" was regenerated with AI and re-sent to ${recipientIds.length} recipient(s).`,
      });

      await resolveTicket(ticket.id);
      await onResolved();
    } catch (error) {
      console.error("Failed to apply feedback:", error);
      alert("Failed to regenerate the policy with AI. Please try again.");
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="card panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <h3 style={{ margin: "0 0 4px" }}>{ticket.title}</h3>
          <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>
            {roleLabel(ticket.role)} · {formatShortDate(ticket.created_at)}
          </p>
        </div>
        <Tag variant="amber">Open</Tag>
      </div>

      <p style={{ margin: "12px 0" }}>{ticket.body}</p>

      {sections.length === 0 ? (
        <p className="sidebar-empty">No sections exist for this role to apply feedback to.</p>
      ) : (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <Input
            value={sectionTitle}
            onChange={(e) => setSectionTitle(e.target.value)}
            placeholder="Section title"
            style={{ maxWidth: 220 }}
          />
          <Button variant="primary" size="sm" onClick={handleApply} disabled={applying}>
            {applying ? (
              <>
                Applying <LoadingDots />
              </>
            ) : (
              "Apply with AI & resend"
            )}
          </Button>
        </div>
      )}
    </div>
  );
}

function ReminderTicketCard({ ticket, onResolved }) {
  const [resolving, setResolving] = useState(false);

  async function handleResolve() {
    if (resolving) return;
    setResolving(true);
    try {
      await resolveTicket(ticket.id);
      await onResolved();
    } catch (error) {
      console.error("Failed to resolve ticket:", error);
      alert("Failed to mark this reminder handled. Please try again.");
    } finally {
      setResolving(false);
    }
  }

  return (
    <div className="card panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <h3 style={{ margin: "0 0 4px" }}>{ticket.title}</h3>
          <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>
            {formatShortDate(ticket.created_at)}
          </p>
        </div>
        <Tag variant="amber">Open</Tag>
      </div>

      <p style={{ margin: "12px 0" }}>{ticket.body}</p>

      <Button variant="secondary" size="sm" onClick={handleResolve} disabled={resolving}>
        {resolving ? "Marking handled..." : "Mark handled"}
      </Button>
    </div>
  );
}

function Tickets() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  async function refresh() {
    setLoadError("");
    try {
      setTickets(await listTickets());
    } catch (err) {
      setLoadError(err.message || "Failed to load tickets. Please try again.");
    }
  }

  useEffect(() => {
    let cancelled = false;

    listTickets()
      .then((data) => {
        if (!cancelled) setTickets(data);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message || "Failed to load tickets. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const open = tickets.filter((t) => t.status === "open" && t.type !== "policy_updated");
  const log = tickets
    .filter((t) => t.type === "policy_updated" || t.status === "resolved")
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  return (
    <div>
      <div className="page-kicker">Tickets</div>
      <h1 style={{ margin: "0 0 6px" }}>Feedback &amp; Reminders</h1>
      <p className="page-lede">
        Manager feedback and signature reminders land here. Applying feedback uses AI to
        regenerate the affected section and automatically re-sends it.
      </p>

      {loadError && <p style={{ color: "var(--color-danger, #c0392b)" }}>{loadError}</p>}

      {loading ? (
        <p className="sidebar-empty">Loading tickets...</p>
      ) : (
        <>
          <h3 style={{ margin: "24px 0 12px" }}>Open ({open.length})</h3>
          {open.length === 0 ? (
            <p className="sidebar-empty">Nothing open.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {open.map((t) =>
                t.type === "feedback" ? (
                  <FeedbackTicketCard key={t.id} ticket={t} onResolved={refresh} />
                ) : (
                  <ReminderTicketCard key={t.id} ticket={t} onResolved={refresh} />
                )
              )}
            </div>
          )}

          {log.length > 0 && (
            <>
              <h3 style={{ margin: "32px 0 12px" }}>Activity log</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13 }}>
                {log.map((t) => (
                  <div key={t.id} style={{ display: "flex", gap: 12 }}>
                    <span style={{ color: "var(--color-text-muted)", minWidth: 90 }}>
                      {formatShortDate(t.created_at)}
                    </span>
                    <span>
                      {t.title} — {t.body.replace(" Notified via email (mock).", "")}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default Tickets;
