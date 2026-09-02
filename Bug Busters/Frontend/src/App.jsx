import { useEffect, useState } from "react";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import HRDashboard from "./pages/HRDashboard";
import EmployeeDashboard from "./pages/EmployeeDashboard";
import ManagerDashboard from "./pages/ManagerDashboard";
import EngineerDashboard from "./pages/EngineerDashboard";
import AccessDenied from "./pages/AccessDenied";
import { getPrefs } from "./Data/store";
import { applyPrefs } from "./utils/applyPrefs";
import { resolveDashboard } from "./roleConfig";
import { getDemoUser, demoLogout } from "./Data/demoAuth";
import "./App.css";

const DASHBOARDS = {
  hr: HRDashboard,
  manager: ManagerDashboard,
  engineer: EngineerDashboard,
  employee: EmployeeDashboard,
};

function App() {
  const [view, setView] = useState("landing"); // "landing" | "login" — only matters while signed out
  const [user, setUser] = useState(() => getDemoUser());

  useEffect(() => {
    applyPrefs(getPrefs());
  }, []);

  function handleLogout() {
    demoLogout();
    setUser(null);
    setView("landing");
  }

  const roles = user ? [user.role] : [];
  const dashboardKey = resolveDashboard(roles);
  const Dashboard = dashboardKey ? DASHBOARDS[dashboardKey] : null;
  const displayIdentity = user?.display_name || user?.email;

  if (!user) {
    return view === "landing" ? (
      <Landing onGetStarted={() => setView("login")} />
    ) : (
      <Login onSignedIn={setUser} />
    );
  }

  return Dashboard ? (
    <Dashboard user={displayIdentity} onLogout={handleLogout} />
  ) : (
    <AccessDenied roles={roles} onLogout={handleLogout} />
  );
}

export default App;
