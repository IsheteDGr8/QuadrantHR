/* =========================================================
   ADMIN AV PORTAL - UNIFIED SHARED COMPONENTS
   Matches exact CSS classes and structure in frontend/css/style.css
   and aligns with Employee & Management Portal sidebar architecture
   ========================================================= */

function getAdminAVPages() {
  return [
    { href: "admin_dashboard.html", title: "Operations Dashboard", subtitle: "HelpDesk Operations & Monitoring" },
    { href: "inbox.html", title: "Triage Inbox", subtitle: "Manage Incoming Requests & Ticket Queue" },
    { href: "submit-ticket.html", title: "Create Ticket", subtitle: "Manual Request Logging" },
    { href: "announcements.html", title: "Announcements", subtitle: "Broadcast System Alerts" },
    { href: "knowledge-base.html", title: "Knowledge Base", subtitle: "Policy & Resolution Articles" },
    { href: "analytics.html", title: "Analytics", subtitle: "Resolution Performance & Metrics" },
    { href: "archive.html", title: "Archive", subtitle: "Resolved Ticket Records" },
    { href: "settings.html", title: "Settings", subtitle: "Admin Portal Configuration" }
  ];
}

function getAdminAVCurrentFilename() {
  return window.location.pathname.split("/").pop() || "admin_dashboard.html";
}

function renderAdminAVSidebar() {
  const sidebarContainer = document.getElementById("shared-sidebar");
  if (!sidebarContainer) return;

  const currentFile = getAdminAVCurrentFilename();

  sidebarContainer.innerHTML = `
    <aside class="sidebar">
      <div class="brand" style="position: relative; justify-content: space-between; width: 100%; padding-right: 15px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="brand-icon">
            <i class="fa-solid fa-ticket"></i>
          </div>
          <div>
            <h2>TicketGenie</h2>
            <span>Admin Operations</span>
          </div>
        </div>
        <button id="brandMenuToggle" class="brand-menu-toggle" aria-label="Toggle Pages">
          <i class="fa-solid fa-bars"></i>
        </button>
      </div>

      <nav class="navigation">
        <div class="nav-title">WORKSPACE</div>
        <a href="admin_dashboard.html" class="nav-item ${currentFile === 'admin_dashboard.html' ? 'active' : ''}">
          <i class="fa-solid fa-gauge-high"></i><span>Operations Dashboard</span>
        </a>
        <a href="inbox.html" class="nav-item ${currentFile === 'inbox.html' ? 'active' : ''}">
          <i class="fa-solid fa-inbox"></i><span>Triage Inbox</span>
        </a>
        <a href="submit-ticket.html" class="nav-item ${currentFile === 'submit-ticket.html' ? 'active' : ''}">
          <i class="fa-solid fa-plus"></i><span>Create Ticket</span>
        </a>

        <div class="nav-title">COMMUNICATION & RESOURCES</div>
        <a href="announcements.html" class="nav-item ${currentFile === 'announcements.html' ? 'active' : ''}">
          <i class="fa-solid fa-bullhorn"></i><span>Announcements</span>
        </a>
        <a href="knowledge-base.html" class="nav-item ${currentFile === 'knowledge-base.html' ? 'active' : ''}">
          <i class="fa-solid fa-book-open"></i><span>Knowledge Base</span>
        </a>

        <div class="nav-title">SYSTEM & RECORDS</div>
        <a href="analytics.html" class="nav-item ${currentFile === 'analytics.html' ? 'active' : ''}">
          <i class="fa-solid fa-chart-pie"></i><span>Analytics</span>
        </a>
        <a href="archive.html" class="nav-item ${currentFile === 'archive.html' ? 'active' : ''}">
          <i class="fa-solid fa-box-archive"></i><span>Archive</span>
        </a>
        <a href="settings.html" class="nav-item ${currentFile === 'settings.html' ? 'active' : ''}">
          <i class="fa-solid fa-sliders"></i><span>Settings</span>
        </a>
        <a href="../employee_NM/index.html" class="nav-item">
          <i class="fa-solid fa-arrow-left"></i><span>Employee View</span>
        </a>
      </nav>

      <div class="sidebar-bottom">
        <div class="system-status">
          <div class="status-dot"></div>
          <div><strong>Admin Operations Live</strong><small>TicketGenie Online</small></div>
        </div>
      </div>
    </aside>
  `;
}

function renderAdminAVTopNav() {
  const topNavContainer = document.getElementById("shared-topnav");
  if (!topNavContainer) return;

  const currentFile = getAdminAVCurrentFilename();
  const pages = getAdminAVPages();
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
          <input type="text" placeholder="Search tickets..." id="globalSearch">
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
            <div class="avatar">AV</div>
            <div class="profile-info"><strong>${user.name || "Admin AV"}</strong><span id="currentRoleDisplay">${user.role || "Operations Admin"}</span></div>
            <i class="fa-solid fa-chevron-down"></i>
          </button>
          <div class="profile-dropdown-menu" id="profileDropdownMenu">
            <span class="dropdown-label">SWITCH PORTAL</span>
            <button type="button" class="role-switch-btn" data-role="Employee">
              <i class="fa-solid fa-user"></i> Employee Portal
            </button>
            <button type="button" class="role-switch-btn active" data-role="Admin">
              <i class="fa-solid fa-shield"></i> Admin Portal
            </button>
          </div>
        </div>
      </div>
    </header>
  `;
}

function initAdminAVInteractiveListeners() {
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
        } else if (selectedRole === "Management") {
          window.location.href = "../management/index.html";
        } else if (selectedRole === "Admin") {
          window.location.href = "admin_dashboard.html";
        }
      });
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderAdminAVSidebar();
  renderAdminAVTopNav();
  initAdminAVInteractiveListeners();
});
