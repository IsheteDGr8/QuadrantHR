import { Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { DirectoryPage } from "./pages/DirectoryPage";
import { HomePage } from "./pages/HomePage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="directory" element={<DirectoryPage />} />
        <Route path="faq" element={<PlaceholderPage moduleId="faq" />} />
        <Route path="helpdesk" element={<PlaceholderPage moduleId="helpdesk" />} />
        <Route path="hiring" element={<PlaceholderPage moduleId="hiring" />} />
        <Route path="training" element={<PlaceholderPage moduleId="training" />} />
        <Route path="policies" element={<PlaceholderPage moduleId="policies" />} />
        <Route path="copilot" element={<PlaceholderPage moduleId="copilot" />} />
      </Route>
    </Routes>
  );
}
