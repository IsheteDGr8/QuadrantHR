import { roleLabel } from "../../Data/store";

function EmployeeSidebar({
  assignments,
  selectedId,
  onSelect,
  onHome,
}) {
  return (
    <div className="sidebar">
      <h2>My Policies</h2>

      {/* Home */}
      <button
        className={
          selectedId === null
            ? "tab tab-active"
            : "tab"
        }
        onClick={onHome}
      >
        Home
      </button>

      {assignments.length === 0 && (
        <p className="sidebar-empty">No policies yet.</p>
      )}

      {assignments.map((assignment) => (
        <button
          key={assignment.id}
          className={
            (assignment.status === "signed"
              ? "tab tab-signed"
              : "tab") +
            (selectedId === assignment.id
              ? " tab-active"
              : "")
          }
          onClick={() => onSelect(assignment)}
        >
          {roleLabel(assignment.role)} Policy

          <span className="tab-status">
            {assignment.status === "signed"
              ? "Signed"
              : "Pending"}
          </span>
        </button>
      ))}
    </div>
  );
}

export default EmployeeSidebar;