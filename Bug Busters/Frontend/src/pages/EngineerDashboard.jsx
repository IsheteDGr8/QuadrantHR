import EmployeeDashboard from "./EmployeeDashboard";

// Engineers get the same read/ask/sign surface as interns — same
// dashboard component, just a different login role.
function EngineerDashboard({ user, onLogout }) {
  return <EmployeeDashboard user={user} onLogout={onLogout} />;
}

export default EngineerDashboard;
