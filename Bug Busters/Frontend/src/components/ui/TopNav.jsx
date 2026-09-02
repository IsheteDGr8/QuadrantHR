// Shared top nav — brand wordmark, Home/Policies/Settings-style tabs,
// and the signed-in user chip. Used across every signed-in dashboard.
function TopNav({ tabs, activeTab, onTabChange, userName, userRole, onLogout }) {
  return (
    <nav className="nav">
      <div className="nav-brand">
        Policy Guardian
        <span className="nav-brand-sub">AI Policy Generator</span>
      </div>

      {tabs.map((tab) => (
        <button
          key={tab.key}
          className={"nav-tab" + (activeTab === tab.key ? " nav-tab-active" : "")}
          onClick={() => onTabChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}

      {userName && (
        <span className="nav-user">
          {userName}
          {userRole ? ` · ${userRole}` : ""}
        </span>
      )}

      {onLogout && (
        <button className="nav-tab nav-logout" onClick={onLogout}>
          Log out
        </button>
      )}
    </nav>
  );
}

export default TopNav;
