import { useState } from "react";
import { getAllRoles, getSelectableRoles, getSections, getAssignments, getExpirationInfo, roleLabel, addRole } from "../Data/store";
import { Input } from "../components/ui/FormControls";
import Button from "../components/ui/Button";
import Tag from "../components/ui/Tag";

// The Policies tab's landing view — an overview across every role that
// has at least one section, with a text search across section content,
// an audience filter, and a "New policy" shortcut into the sidebar's
// role-creation flow.
//
// The mockup also has a "Filters" button and a peer-benchmark blurb.
// "Filters" duplicates the audience chips below with no clear extra
// behavior of its own, and there's no peer data source to draw a real
// benchmark from — fabricating one would be worse than leaving it out —
// so both stay out until there's something real to back them.
function PolicyLibrary({ onOpenRole }) {
  const [query, setQuery] = useState("");
  const [audience, setAudience] = useState(null); // null ("Everyone") | role id
  const [addingRole, setAddingRole] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");

  const allSections = getSections();
  const allAssignments = getAssignments();
  const q = query.trim().toLowerCase();
  const roles = getAllRoles();

  // Narrower than `roles` above (which also has to surface legacy role
  // ids still attached to existing sections, e.g. old "lead"/"employee"
  // tags from before those were removed as selectable roles — see
  // getSelectableRoles' own comment in Data/store.js). The Audience
  // filter is meant to offer real, currently-assignable audiences, not
  // resurrect every id a policy has ever been tagged with. Engineer is
  // excluded from this filter specifically per request — it stays a
  // real role/dashboard everywhere else (roleConfig.js, EngineerDashboard,
  // demo login accounts); it's just not offered as an audience here.
  const audienceRoles = getSelectableRoles().filter((role) => role.id !== "engineer");

  const rows = roles
    .map((role) => {
      const roleSections = allSections.filter((s) => s.role === role.id);
      if (roleSections.length === 0) return null;

      const roleAssignments = allAssignments.filter((a) => a.role === role.id);
      const signed = roleAssignments.filter((a) => a.status === "signed").length;
      const coverage = roleAssignments.length === 0 ? null : Math.round((signed / roleAssignments.length) * 100);

      const soonest = roleSections
        .map((s) => ({ section: s, info: getExpirationInfo(s) }))
        .sort((a, b) => a.info.daysRemaining - b.info.daysRemaining)[0];

      // A real, non-fabricated stand-in for "version": how many saved
      // revisions this role's sections collectively have, plus the
      // original save.
      const version = 1 + roleSections.reduce((sum, s) => sum + (s.history || []).length, 0);

      return { role, roleSections, coverage, soonest, version };
    })
    .filter(Boolean)
    .filter((row) => !audience || row.role.id === audience)
    .filter((row) => {
      if (!q) return true;
      if (row.role.label.toLowerCase().includes(q)) return true;
      return row.roleSections.some(
        (s) => s.title.toLowerCase().includes(q) || s.content.toLowerCase().includes(q)
      );
    });

  function handleCreateRole(e) {
    e.preventDefault();
    const id = addRole(newRoleName);
    if (!id) return;
    setNewRoleName("");
    setAddingRole(false);
    onOpenRole?.(id);
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20, flexWrap: "wrap" }}>
        <Input
          placeholder='Search policy text, e.g. "monitor allowance"'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ maxWidth: 420, flex: "1 1 260px" }}
        />
        <Button variant="primary" onClick={() => setAddingRole((v) => !v)} style={{ marginLeft: "auto" }}>
          New policy
        </Button>
      </div>

      {addingRole && (
        <form
          onSubmit={handleCreateRole}
          style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 20 }}
        >
          <Input
            autoFocus
            placeholder="Who is this policy for? e.g. Contractor"
            value={newRoleName}
            onChange={(e) => setNewRoleName(e.target.value)}
            style={{ maxWidth: 300 }}
          />
          <Button variant="primary" type="submit" disabled={!newRoleName.trim()}>
            Create
          </Button>
          <Button variant="secondary" type="button" onClick={() => setAddingRole(false)}>
            Cancel
          </Button>
        </form>
      )}

      <div style={{ marginBottom: 24 }}>
        <div className="page-kicker" style={{ marginBottom: 10 }}>Audience</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Button variant={audience === null ? "primary" : "secondary"} onClick={() => setAudience(null)}>
            Everyone
          </Button>
          {audienceRoles.map((role) => (
            <Button
              key={role.id}
              variant={audience === role.id ? "primary" : "secondary"}
              onClick={() => setAudience(role.id)}
            >
              {role.label}
            </Button>
          ))}
        </div>
      </div>

      <h3 style={{ margin: "0 0 16px" }}>
        {rows.length} live polic{rows.length === 1 ? "y" : "ies"}
      </h3>

      {rows.length === 0 ? (
        <p className="sidebar-empty">
          {q || audience ? "No policies match that filter." : "No policies yet — build one from the sidebar."}
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Policy</th>
              <th>Version</th>
              <th>Sections</th>
              <th>Expires</th>
              <th style={{ textAlign: "right" }}>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ role, roleSections, coverage, soonest, version }) => (
              <tr
                key={role.id}
                onClick={() => onOpenRole?.(role.id)}
                style={{ cursor: onOpenRole ? "pointer" : "default" }}
              >
                <td data-label="Policy" style={{ fontWeight: 600 }}>{roleLabel(role.id)}</td>
                <td data-label="Version">v{version}</td>
                <td data-label="Sections">{roleSections.length}</td>
                <td data-label="Expires">
                  {!soonest ? (
                    "—"
                  ) : soonest.info.status === "overdue" ? (
                    <Tag variant="accent-2">Review overdue</Tag>
                  ) : soonest.info.status === "soon" ? (
                    <Tag variant="accent-2">{soonest.info.daysRemaining}d left</Tag>
                  ) : (
                    `${soonest.info.daysRemaining}d left`
                  )}
                </td>
                <td data-label="Coverage" style={{ textAlign: "right" }}>{coverage === null ? "Not sent" : `${coverage}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default PolicyLibrary;
