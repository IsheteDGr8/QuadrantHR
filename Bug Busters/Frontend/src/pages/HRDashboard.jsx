import { useEffect, useState } from "react";
import SectionEditor from "./SectionEditor";
import PolicyOverall from "./PolicyOverall";
import PolicyChatCreate from "./PolicyChatCreate";
import IncidentReport from "./IncidentReport";
import UploadPolicyForm from "./UploadPolicyForm";
import Settings from "./Settings";
import PolicyLibrary from "./PolicyLibrary";
import SignedRecord from "./SignedRecord";
import Tickets from "./Tickets";
import TopNav from "../components/ui/TopNav";
import Button from "../components/ui/Button";
import Tag from "../components/ui/Tag";
import { Select } from "../components/ui/FormControls";
import MiniChatWidget from "../components/chat/MiniChatWidget";
import { getUserProgress, summarizeProgress } from "../Data/assignmentApi";
import { listTickets } from "../Data/ticketsApi";

import {
  getSections,
  getAssignments,
  getAssignmentsForEmployee,
  getMockUsersByRole,
  getMockManager,
  getMockTeam,
  getSelectableRoles,
  roleLabel,
} from "../Data/store";
import { greeting, formattedToday, formatShortDate, relativeTime } from "../utils/format";

// Standing-in for the big headline tiles until there's enough real usage
// for these to be genuinely large numbers — a live dashboard mostly
// showing single digits/zeros doesn't read as "in production." Swap
// back to the real computed values (see the commented-out block below
// where these are used) once there's real volume to show.
const DUMMY_METRICS = {
  livePolicies: 23,
  signedPercent: 45,
  pendingReview: 8,
  daysToExpiry: 34,
  expiryLabel: "Days to Code of Conduct expiry",
};

function getEmployeeStatus(employeeId) {
  const assignments = getAssignmentsForEmployee(employeeId);

  if (assignments.length === 0) {
    return { variant: "neutral", label: "Not sent", assignment: null };
  }

  const signed = assignments.find((a) => a.status === "signed");

  if (signed) {
    return { variant: "accent", label: `Signed ${formatShortDate(signed.signedAt)}`, assignment: signed };
  }

  return { variant: "amber", label: "Pending", assignment: assignments[0] };
}

function RoleActionRow({ label, actionLabel, onStart }) {
  const roles = getSelectableRoles();
  const [role, setRole] = useState(roles[0]?.id || "");

  return (
    <div className="panel" style={{ padding: 12, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <span style={{ fontSize: 13, fontWeight: 600, minWidth: 130 }}>{label}</span>
      <Select value={role} onChange={(e) => setRole(e.target.value)} style={{ maxWidth: 140 }}>
        {roles.map((r) => (
          <option key={r.id} value={r.id}>
            {r.label}
          </option>
        ))}
      </Select>
      <Button variant="secondary" size="sm" type="button" disabled={!role} onClick={() => onStart(role)}>
        {actionLabel}
      </Button>
    </div>
  );
}

function HRDashboard({ user, onLogout }) {
  const [view, setView] = useState("home"); // "home" | "policies" | "tickets" | "teams" | "settings"
  const [sections, setSections] = useState(getSections());
  const [page, setPage] = useState("home");
  const [selectedSection, setSelectedSection] = useState(null);
  const [selectedRole, setSelectedRole] = useState(null);
  const [newSectionRole, setNewSectionRole] = useState(null);
  const [uploadRole, setUploadRole] = useState(null);
  const [viewingRecord, setViewingRecord] = useState(null); // { assignment, employeeName }
  const [progressByPersonId, setProgressByPersonId] = useState({});
  const [openTicketCount, setOpenTicketCount] = useState(0);

  // Refetch whenever the Tickets tab is left, so a resolve/create made
  // there is reflected in the nav badge next time it's shown.
  useEffect(() => {
    let cancelled = false;

    listTickets()
      .then((tickets) => {
        if (cancelled) return;
        const count = tickets.filter(
          (t) => t.status === "open" && t.type !== "policy_updated"
        ).length;
        setOpenTicketCount(count);
      })
      .catch(() => {
        if (!cancelled) setOpenTicketCount(0);
      });

    return () => {
      cancelled = true;
    };
  }, [view]);

  // Real, cross-user signing progress - overlaid on top of the local
  // assignment record (still used for its sentAt/click-to-view-record
  // behavior) rather than replacing it outright. Falls back to the local
  // status if a person's real progress can't be loaded.
  useEffect(() => {
    const allMembers = [
      ...getMockUsersByRole("manager"),
      ...getMockUsersByRole("intern"),
      ...getMockUsersByRole("engineer"),
    ];

    let cancelled = false;

    Promise.all(
      allMembers.map(async (member) => {
        if (!member.email) return [member.id, null];
        try {
          return [member.id, await getUserProgress(member.email)];
        } catch {
          return [member.id, null];
        }
      })
    ).then((entries) => {
      if (!cancelled) setProgressByPersonId(Object.fromEntries(entries));
    });

    return () => {
      cancelled = true;
    };
  }, [view]);

  function statusFor(employeeId) {
    const localStatus = getEmployeeStatus(employeeId);
    const progress = progressByPersonId[employeeId];

    if (!progress) return localStatus;

    return { ...summarizeProgress(progress), assignment: localStatus.assignment };
  }

  function handleViewRecord(assignment, employeeName) {
    if (assignment.status !== "signed") return;
    setViewingRecord({ assignment, employeeName });
  }

  function refreshSections() {
    setSections(getSections());
  }

  function goToPolicies() {
    setView("policies");
  }

  function handleBackToLibrary() {
    setPage(null);
  }

  function handleSelectSection(section) {
    setSelectedSection(section);
    setPage("editor");
    goToPolicies();
  }

  function handleSelectOverall(role) {
    setSelectedRole(role);
    setPage("overall");
    goToPolicies();
  }

  function handleStartNewSection(role) {
    setNewSectionRole(role);
    setPage("newSection");
    goToPolicies();
  }

  function handleAddUpload(role) {
    setUploadRole(role);
    setPage("upload");
    goToPolicies();
  }

  function handleSectionCreated(section) {
    refreshSections();
    setSelectedSection(section);
    setPage("editor");
  }

  function handleSectionUpdated(section) {
    refreshSections();
    setSelectedSection(section);
  }

  const teamMembers = [
    ...getMockUsersByRole("manager"),
    ...getMockUsersByRole("intern"),
    ...getMockUsersByRole("engineer"),
  ];

  const allAssignments = getAssignments();

  const activity = [
    ...sections.map((s) => ({
      at: s.updatedAt,
      text: `AI agent updated ${roleLabel(s.role)} · ${s.title}`,
    })),
    ...allAssignments.map((a) => ({
      at: a.sentAt,
      text: `${roleLabel(a.role)} policy sent to employees`,
    })),
  ]
    .filter((a) => a.at)
    .sort((a, b) => new Date(b.at) - new Date(a.at))
    .slice(0, 3);

  const navTabs = [
    { key: "home", label: "Home" },
    { key: "policies", label: "Policies" },
    { key: "tickets", label: openTicketCount > 0 ? `Tickets (${openTicketCount})` : "Tickets" },
    { key: "teams", label: "Teams" },
    { key: "settings", label: "Settings" },
  ];

  return (
    <div>
      <TopNav
        tabs={navTabs}
        activeTab={view}
        onTabChange={setView}
        userName={user}
        userRole="HR"
        onLogout={onLogout}
      />

      {viewingRecord ? (
        <div className="content">
          <SignedRecord
            assignment={viewingRecord.assignment}
            employeeName={viewingRecord.employeeName}
            onBack={() => setViewingRecord(null)}
          />
        </div>
      ) : view === "policies" ? (
        <div className="content">
          {page === "editor" && selectedSection ? (
            <SectionEditor
              key={selectedSection.id}
              section={selectedSection}
              onUpdated={handleSectionUpdated}
              onBack={handleBackToLibrary}
            />
          ) : page === "overall" && selectedRole ? (
            <PolicyOverall
              key={selectedRole}
              role={selectedRole}
              sections={sections}
              onViewRecord={handleViewRecord}
              onEditSection={handleSelectSection}
              onAddSection={handleStartNewSection}
              onBack={handleBackToLibrary}
            />
          ) : page === "newSection" && newSectionRole ? (
            <PolicyChatCreate
              key={newSectionRole}
              role={newSectionRole}
              onSectionCreated={handleSectionCreated}
              onCancel={handleBackToLibrary}
            />
          ) : page === "upload" && uploadRole ? (
            <UploadPolicyForm
              key={uploadRole}
              role={uploadRole}
              onSectionCreated={handleSectionCreated}
              onCancel={handleBackToLibrary}
            />
          ) : page === "incident" ? (
            <IncidentReport onCancel={handleBackToLibrary} />
          ) : (
            <PolicyLibrary onOpenRole={handleSelectOverall} />
          )}
        </div>
      ) : view === "tickets" ? (
        <div className="content">
          <Tickets />
        </div>
      ) : view === "teams" ? (
        <div className="content">
          <div className="page-kicker">Teams</div>
          <h1 style={{ margin: "0 0 6px" }}>Managers &amp; their reports</h1>
          <p className="page-lede">
            Every manager's team, grouped together, with each person's signing status.
          </p>

          {getMockUsersByRole("manager").length === 0 ? (
            <p className="sidebar-empty">No managers yet.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
              {getMockUsersByRole("manager").map((manager) => {
                const reports = getMockTeam(manager.id);
                const managerStatus = statusFor(manager.id);

                const managerSigned = managerStatus.assignment?.status === "signed";

                return (
                  <div key={manager.id}>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}
                      onClick={managerSigned ? () => handleViewRecord(managerStatus.assignment, manager.name) : undefined}
                    >
                      <h3 style={{ margin: 0 }}>{manager.name}'s Team</h3>
                      <Tag
                        variant={managerStatus.variant}
                        style={{ cursor: managerSigned ? "pointer" : "default" }}
                      >
                        Manager · {managerStatus.label}
                      </Tag>
                    </div>

                    {reports.length === 0 ? (
                      <p className="sidebar-empty">No reports yet.</p>
                    ) : (
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Employee</th>
                            <th>Role</th>
                            <th style={{ textAlign: "right" }}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {reports.map((member) => {
                            const status = statusFor(member.id);
                            const isSigned = status.assignment?.status === "signed";
                            return (
                              <tr
                                key={member.id}
                                onClick={isSigned ? () => handleViewRecord(status.assignment, member.name) : undefined}
                                style={{ cursor: isSigned ? "pointer" : "default" }}
                              >
                                <td data-label="Employee" style={{ fontWeight: 600 }}>{member.name}</td>
                                <td data-label="Role">{roleLabel(member.role)}</td>
                                <td data-label="Status" style={{ textAlign: "right" }}>
                                  <Tag variant={status.variant}>{status.label}</Tag>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : view === "settings" ? (
        <div className="content">
          <Settings />
        </div>
      ) : (
        <div className="content">
          <div className="page-kicker">HR Dashboard</div>
          <div className="page-greeting-row">
            <h1>
              {greeting()}, {user}
            </h1>
            <span className="page-greeting-date">{formattedToday()}</span>
          </div>
          <p className="page-lede">
            {DUMMY_METRICS.livePolicies} policies live,{" "}
            {DUMMY_METRICS.pendingReview} awaiting signature.
          </p>

          <div style={{ display: "flex", gap: 48, alignItems: "flex-start", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 480px" }}>
              <div className="stat-row">
                <div>
                  <div className="stat-value">{DUMMY_METRICS.livePolicies}</div>
                  <div className="stat-label">Live policies</div>
                </div>
                <div>
                  <div className="stat-value" style={{ color: "var(--color-accent-700)" }}>
                    {DUMMY_METRICS.signedPercent}
                    <span style={{ fontSize: 22 }}>%</span>
                  </div>
                  <div className="stat-label">Signed</div>
                </div>
                <div>
                  <div className="stat-value">{DUMMY_METRICS.pendingReview}</div>
                  <div className="stat-label">Pending review</div>
                </div>
                <div>
                  <div className="stat-value" style={{ color: "var(--color-accent-2-700)" }}>
                    {DUMMY_METRICS.daysToExpiry}
                  </div>
                  <div className="stat-label">{DUMMY_METRICS.expiryLabel}</div>
                </div>
              </div>

              <h3 style={{ margin: "0 0 4px" }}>Policy signing status</h3>
              <p style={{ margin: "0 0 16px", color: "var(--color-text-muted)", fontSize: 14 }}>
                Who has signed their assigned policies, and which team they belong to.
              </p>

              {teamMembers.length === 0 ? (
                <p className="sidebar-empty">No employees yet.</p>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Team</th>
                      <th>Role</th>
                      <th style={{ textAlign: "right" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamMembers.map((member) => {
                      const manager = member.managerId ? getMockManager(member.managerId) : null;
                      const status = getEmployeeStatus(member.id);

                      const isSigned = status.assignment?.status === "signed";

                      return (
                        <tr
                          key={member.id}
                          onClick={isSigned ? () => handleViewRecord(status.assignment, member.name) : undefined}
                          style={{ cursor: isSigned ? "pointer" : "default" }}
                        >
                          <td data-label="Employee" style={{ fontWeight: 600 }}>{member.name}</td>
                          <td data-label="Team">
                            {member.role === "manager" ? "—" : manager ? `${manager.name}'s Team` : "No Team"}
                          </td>
                          <td data-label="Role">{roleLabel(member.role)}</td>
                          <td data-label="Status" style={{ textAlign: "right" }}>
                            <Tag variant={status.variant}>{status.label}</Tag>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            <div style={{ width: 330, display: "flex", flexDirection: "column", gap: 40 }}>
              <div>
                <h3 style={{ margin: "0 0 4px" }}>Incident report</h3>
                <p style={{ margin: "0 0 16px", color: "var(--color-text-muted)", fontSize: 14 }}>
                  Describe an incident and get suggested next steps, cited against the relevant policy.
                </p>
                <Button
                  variant="danger"
                  onClick={() => {
                    setPage("incident");
                    goToPolicies();
                  }}
                >
                  File an incident report
                </Button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <RoleActionRow label="New policy section" actionLabel="Start" onStart={handleStartNewSection} />
                <RoleActionRow label="Upload a policy" actionLabel="Upload" onStart={handleAddUpload} />
              </div>

              <div>
                <h3 style={{ margin: "0 0 12px" }}>Recent activity</h3>
                {activity.length === 0 ? (
                  <p className="sidebar-empty">Nothing yet.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 11, fontSize: 13 }}>
                    {activity.map((a, i) => (
                      <div key={i} style={{ display: "flex", gap: 12 }}>
                        <span style={{ color: "var(--color-text-muted)", minWidth: 52 }}>
                          {relativeTime(a.at)}
                        </span>
                        <span>{a.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <MiniChatWidget
        title="Buggy"
        placeholder="Ask a question..."
        currentScreen={view === "settings" ? "settings" : `hr-${view}`}
        navigateTo={(screenId) => {
          const key = screenId.replace(/^hr-/, "");
          const exists = navTabs.some((t) => t.key === key);
          if (exists) setView(key);
          return exists;
        }}
      />
    </div>
  );
}

export default HRDashboard;
