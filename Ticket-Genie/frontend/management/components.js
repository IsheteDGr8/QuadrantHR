/* =========================================================
   MANAGEMENT PORTAL - UNIFIED SHARED COMPONENTS
   Matches exact CSS classes and structure in frontend/css/style.css
   and aligns with Employee NM Portal sidebar architecture
   ========================================================= */

function getManagementPages() {
  return [
    { href: "index.html", title: "SuperAdmin Dashboard", subtitle: "Enterprise Control Center & Telemetry" },
    { href: "inbox.html", title: "Unified Inbox & Triage", subtitle: "Upper Management & Multi-Dept Queue" },
    { href: "submit-ticket.html", title: "Create Ticket", subtitle: "Executive & Manager Ticket Logging" },
    { href: "departments.html", title: "Departments & RBAC", subtitle: "Manage Enterprise Queues & M365 Object IDs" },
    { href: "hr-portal.html", title: "HR Operations Portal", subtitle: "HR Department Request Management" },
    { href: "it-portal.html", title: "IT Operations Portal", subtitle: "IT Department Infrastructure Management" },
    { href: "knowledge-base.html", title: "Knowledge Ingestion", subtitle: "Grow Ticketer RAG Knowledge Memory Permanently" },
    { href: "analytics.html", title: "HR Analytics & Resolution Trends", subtitle: "Real-Time Helpdesk Metrics and SLA Performance" },
    { href: "settings.html", title: "System Settings", subtitle: "Configure Governance & Security Parameters" }
  ];
}

function getManagementCurrentFilename() {
  return window.location.pathname.split("/").pop() || "index.html";
}

function renderManagementSidebar() {
  const sidebarContainer = document.getElementById("shared-sidebar");
  if (!sidebarContainer) return;

  const currentFile = getManagementCurrentFilename();

  sidebarContainer.innerHTML = `
    <aside class="sidebar">
      <div class="brand" style="position: relative; justify-content: space-between; width: 100%; padding-right: 15px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="brand-icon">
            <i class="fa-solid fa-ticket"></i>
          </div>
          <div>
            <h2>TicketGenie</h2>
            <span>Management Portal</span>
          </div>
        </div>
        <button id="brandMenuToggle" class="brand-menu-toggle" aria-label="Toggle Pages">
          <i class="fa-solid fa-bars"></i>
        </button>
      </div>

      <nav class="navigation">
        <div class="nav-title">MANAGEMENT & WORKFORCE</div>
        <a href="index.html" class="nav-item ${currentFile === 'index.html' ? 'active' : ''}">
          <i class="fa-solid fa-gauge-high"></i><span>SuperAdmin Dashboard</span>
        </a>
        <a href="inbox.html" class="nav-item ${currentFile === 'inbox.html' ? 'active' : ''}">
          <i class="fa-solid fa-inbox"></i><span>Inbox & Triage</span>
        </a>
        <a href="submit-ticket.html" class="nav-item ${currentFile === 'submit-ticket.html' ? 'active' : ''}">
          <i class="fa-solid fa-plus"></i><span>Create Ticket</span>
        </a>

        <div class="nav-title">PORTALS & QUEUES</div>
        <a href="departments.html" class="nav-item ${currentFile === 'departments.html' ? 'active' : ''}">
          <i class="fa-solid fa-building-user"></i><span>Departments & RBAC</span>
        </a>
        <a href="hr-portal.html" class="nav-item ${currentFile === 'hr-portal.html' ? 'active' : ''}">
          <i class="fa-solid fa-user-tie"></i><span>HR Portal</span>
        </a>
        <a href="it-portal.html" class="nav-item ${currentFile === 'it-portal.html' ? 'active' : ''}">
          <i class="fa-solid fa-laptop-code"></i><span>IT Portal</span>
        </a>

        <div class="nav-title">INTELLIGENCE & RAG</div>
        <a href="knowledge-base.html" class="nav-item ${currentFile === 'knowledge-base.html' ? 'active' : ''}">
          <i class="fa-solid fa-book-open"></i><span>Knowledge Ingestion</span>
        </a>
        <a href="analytics.html" class="nav-item ${currentFile === 'analytics.html' ? 'active' : ''}">
          <i class="fa-solid fa-chart-pie"></i><span>HR Analytics</span>
        </a>

        <div class="nav-title">GOVERNANCE</div>
        <a href="settings.html" class="nav-item ${currentFile === 'settings.html' ? 'active' : ''}">
          <i class="fa-solid fa-sliders"></i><span>System Settings</span>
        </a>
        <a href="../employee_NM/index.html" class="nav-item">
          <i class="fa-solid fa-arrow-left"></i><span>Employee Portal</span>
        </a>
      </nav>

      <div class="sidebar-bottom">
        <div class="system-status">
          <div class="status-dot"></div>
          <div><strong>Azure Telemetry Live</strong><small>TicketGenie Ops Online</small></div>
        </div>
      </div>
    </aside>
  `;
}

function renderManagementTopNav() {
  const topNavContainer = document.getElementById("shared-topnav");
  if (!topNavContainer) return;

  const currentFile = getManagementCurrentFilename();
  const pages = getManagementPages();
  const activePage = pages.find(p => p.href === currentFile) || pages[0];
  const user = JSON.parse(localStorage.getItem("portalUser") || '{}');

  topNavContainer.innerHTML = `
    <header class="topbar">
      <div class="header-left" style="display: flex; align-items: center; gap: 20px;">
        <button class="icon-button" id="sidebarToggle" type="button" aria-label="Toggle Sidebar">
          <i class="fa-solid fa-bars"></i>
        </button>
        <div class="page-title">
          <h1>${activePage.title}</h1>
        </div>
      </div>

      <div class="topbar-actions">
        <div class="search-box">
          <i class="fa-solid fa-magnifying-glass"></i>
          <input type="text" placeholder="Search tickets, SQL..." id="globalSearch">
          <span class="shortcut">⌘ K</span>
        </div>
        <button class="icon-button" id="darkModeToggle" type="button" aria-label="Toggle Dark Mode">
          <i class="fa-solid fa-moon" id="darkModeIcon"></i>
        </button>
        <button class="icon-button" type="button">
          <i class="fa-regular fa-bell"></i><span class="notification-dot"></span>
        </button>
        <div class="profile">
          <button class="profile-button" id="profileDropdownTrigger" aria-haspopup="menu" aria-expanded="false">
            <div class="avatar">SS</div>
            <div class="profile-info"><strong>${user.name || "SuperAdmin SS"}</strong><span id="currentRoleDisplay">${user.role || "Super Admin"}</span></div>
            <i class="fa-solid fa-chevron-down"></i>
          </button>
          <div class="profile-dropdown-menu" id="profileDropdownMenu">
            <span class="dropdown-label">SWITCH PORTAL</span>
            <button type="button" class="role-switch-btn" data-role="Employee">
              <i class="fa-solid fa-user"></i> Employee Portal
            </button>
            <button type="button" class="role-switch-btn active" data-role="Management">
              <i class="fa-solid fa-shield-halved"></i> Management Portal
            </button>
          </div>
        </div>
      </div>
    </header>
  `;
}

function initManagementInteractiveListeners() {
  const sidebarToggle = document.getElementById("sidebarToggle");
  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      document.body.classList.toggle("sidebar-closed");
    });
  }

  const brandMenuToggle = document.getElementById("brandMenuToggle");
  if (brandMenuToggle) {
    brandMenuToggle.addEventListener("click", () => {
      document.body.classList.toggle("sidebar-closed");
    });
  }

  const darkModeToggle = document.getElementById("darkModeToggle");
  if (darkModeToggle) {
    darkModeToggle.addEventListener("click", () => {
      document.body.classList.toggle("dark-mode");
      const icon = document.getElementById("darkModeIcon");
      if (icon) {
        if (document.body.classList.contains("dark-mode")) {
          icon.classList.remove("fa-moon");
          icon.classList.add("fa-sun");
        } else {
          icon.classList.remove("fa-sun");
          icon.classList.add("fa-moon");
        }
      }
    });
  }

  const profileBtn = document.getElementById("profileDropdownTrigger");
  const profileMenu = document.getElementById("profileDropdownMenu");
  if (profileBtn && profileMenu) {
    profileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isShowing = profileMenu.classList.toggle("show");
      profileBtn.setAttribute("aria-expanded", isShowing);
    });

    document.addEventListener("click", (e) => {
      if (!profileBtn.contains(e.target) && !profileMenu.contains(e.target)) {
        profileMenu.classList.remove("show");
        profileBtn.setAttribute("aria-expanded", "false");
      }
    });

    const roleButtons = profileMenu.querySelectorAll(".role-switch-btn");
    roleButtons.forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const selectedRole = btn.getAttribute("data-role");
        if (selectedRole === "Employee") {
          window.location.href = "../employee_NM/index.html";
        } else if (selectedRole === "Admin") {
          window.location.href = "../admin_AV/admin_dashboard.html";
        } else if (selectedRole === "Management") {
          window.location.href = "index.html";
        }
      });
    });
  }
}

function renderGenieWidget() {
  if (document.getElementById("genieButton") || document.getElementById("genieChat")) return;
  const genieContainer = document.createElement("div");
  genieContainer.className = "genie-container";
  genieContainer.innerHTML = `
    <button class="genie-button" id="genieButton" type="button"><i class="ph-fill ph-magic-wand"></i> Ask Genie</button>
    <div class="genie-chat" id="genieChat">
      <div class="genie-chat-header">
        <div class="genie-header-info">
          <div class="genie-avatar"><i class="ph-fill ph-magic-wand"></i></div>
          <div><strong>Genie AI</strong><span><span class="genie-status-dot"></span> Online</span></div>
        </div>
        <button class="genie-close" id="closeGenieButton" type="button"><i class="ph ph-x"></i></button>
      </div>
      <div class="genie-messages" id="genieMessages">
        <div class="genie-message">
          <div class="genie-message-avatar"><i class="ph-fill ph-magic-wand"></i></div>
          <div class="genie-bubble">Hi! I'm Genie. I can help you manage tickets, query policies, or guide you through SuperAdmin tasks.</div>
        </div>
        <div class="genie-suggestions">
          <button class="genie-suggestion" type="button">Check tickets</button>
          <button class="genie-suggestion" type="button">Bulk approve leave</button>
          <button class="genie-suggestion" type="button">Find policies</button>
        </div>
      </div>
      <div class="genie-input-area">
        <input type="text" id="genieInput" placeholder="Ask Genie something..." autocomplete="off">
        <button type="button" id="genieSendButton"><i class="ph-fill ph-arrow-up"></i></button>
      </div>
      <div class="genie-disclaimer">Genie may occasionally provide inaccurate information.</div>
    </div>
  `;
  document.body.appendChild(genieContainer);
}

// Backwards compatibility helper
function initSharedComponents() {
  renderManagementSidebar();
  renderManagementTopNav();
  initManagementInteractiveListeners();
  renderGenieWidget();
  if (typeof initializeGenie === "function") initializeGenie();
}

document.addEventListener("DOMContentLoaded", () => {
  if (window.AzureAuth && typeof window.AzureAuth.enforcePageAccessControl === "function") {
    if (!window.AzureAuth.enforcePageAccessControl()) return;
  }
  renderManagementSidebar();
  renderManagementTopNav();
  initManagementInteractiveListeners();
  renderGenieWidget();
  if (typeof initializeGenie === "function") initializeGenie();
});
