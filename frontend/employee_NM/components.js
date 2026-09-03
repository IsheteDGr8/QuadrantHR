console.log("%c[TicketGenie Components.js] Script file loaded!", "color: #3b82f6; font-weight: bold; font-size: 14px;");

/* =========================================================
   EMPLOYEE NM PORTAL - UNIFIED SHARED COMPONENTS
   ========================================================= */

function getEmployeePages() {
  return [
    { href: "index.html", title: "Help & Support" },
    { href: "new-request.html", title: "New Support Request" },
    { href: "my-tickets.html", title: "My Tickets" },
    { href: "knowledge-base.html", title: "Knowledge Base" },
    { href: "announcements.html", title: "Announcements" },
    { href: "notifications.html", title: "Notifications" },
    { href: "profile.html", title: "Profile & Credentials" },
    { href: "ticket-detail.html", title: "Ticket Details" }
  ];
}

function getEmployeeCurrentFilename() {
  return window.location.pathname.split("/").pop() || "index.html";
}

function renderEmployeeNMSidebar() {
  const sidebarContainer = document.getElementById("shared-sidebar");
  if (!sidebarContainer) return;

  const currentFile = getEmployeeCurrentFilename();

  sidebarContainer.innerHTML = `
    <aside class="sidebar">
      <div class="brand" style="position: relative; justify-content: space-between; width: 100%; padding-right: 15px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div class="brand-icon">
            <i class="fa-solid fa-ticket"></i>
          </div>
          <div>
            <h2>TicketGenie</h2>
            <span>Employee Portal</span>
          </div>
        </div>
        <button id="brandMenuToggle" class="brand-menu-toggle" aria-label="Toggle Pages">
          <i class="fa-solid fa-bars"></i>
        </button>
      </div>

      <nav class="navigation">
        <div class="nav-title">WORKSPACE</div>
        <a href="index.html" class="nav-item ${currentFile === 'index.html' ? 'active' : ''}">
          <i class="fa-solid fa-house"></i><span>Help & Support</span>
        </a>
        <a href="my-tickets.html" class="nav-item ${currentFile === 'my-tickets.html' ? 'active' : ''}">
          <i class="fa-solid fa-ticket"></i><span>My Tickets</span>
        </a>
        <a href="new-request.html" class="nav-item ${currentFile === 'new-request.html' ? 'active' : ''}">
          <i class="fa-solid fa-plus"></i><span>New Request</span>
        </a>

        <div class="nav-title">TIME OFF & COMPANY</div>
        <a href="announcements.html" class="nav-item ${currentFile === 'announcements.html' ? 'active' : ''}">
          <i class="fa-solid fa-bullhorn"></i><span>Announcements</span>
        </a>

        <div class="nav-title">RESOURCES</div>
        <a href="knowledge-base.html" class="nav-item ${currentFile === 'knowledge-base.html' ? 'active' : ''}">
          <i class="fa-solid fa-book-open"></i><span>Knowledge Base</span>
        </a>
        <a href="notifications.html" class="nav-item ${currentFile === 'notifications.html' ? 'active' : ''}">
          <i class="fa-solid fa-bell"></i><span>Notifications</span><span class="notification-count">3</span>
        </a>
        <a href="profile.html" class="nav-item ${currentFile === 'profile.html' ? 'active' : ''}">
          <i class="fa-solid fa-user-gear"></i><span>Profile & Credentials</span>
        </a>
      </nav>

      <div class="sidebar-bottom">
        <div class="system-status">
          <div class="status-dot"></div>
          <div><strong>All systems operational</strong><small>TicketGenie is online</small></div>
        </div>
      </div>
    </aside>
  `;
}

function renderEmployeeNMTopNav() {
  const topNavContainer = document.getElementById("shared-topnav");
  if (!topNavContainer) return;

  const currentFile = getEmployeeCurrentFilename();
  const pages = getEmployeePages();
  const activePage = pages.find(p => p.href === currentFile) || pages[0];
  const user = JSON.parse(localStorage.getItem("portalUser") || '{}');
  const displayName = user.name || "Employee";
  const initials = user.avatar || (displayName.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2) || "EM");
  const displayRole = user.role || "Employee";

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
          <input type="text" placeholder="Search..." id="globalSearch">
          <span class="shortcut">⌘ K</span>
        </div>
        <button class="icon-button" id="myCustomDarkToggle" type="button" aria-label="Toggle Dark Mode">
          <i class="fa-solid fa-moon" id="moonIcon"></i>
          <i class="fa-solid fa-sun" id="sunIcon" style="color: #f59e0b; display: none;"></i>
        </button>
        <button class="icon-button" type="button">
          <i class="fa-regular fa-bell"></i><span class="notification-dot"></span>
        </button>
        <div class="profile">
          <button class="profile-button" id="profileDropdownTrigger" aria-haspopup="menu" aria-expanded="false">
            <div class="avatar" id="topNavAvatar">${initials}</div>
            <div class="profile-info"><strong id="topNavUserName">${displayName}</strong><span id="currentRoleDisplay">${displayRole}</span></div>
            <i class="fa-solid fa-chevron-down"></i>
          </button>
        </div>
      </div>
    </header>
  `;

  // Asynchronously fetch profile from backend DB if available
  if (typeof apiFetchUserProfile === "function") {
    apiFetchUserProfile().then(profile => {
      if (profile && profile.name) {
        const nameElem = document.getElementById("topNavUserName");
        const avatarElem = document.getElementById("topNavAvatar");
        const roleElem = document.getElementById("currentRoleDisplay");
        if (nameElem) nameElem.textContent = profile.name;
        if (roleElem && profile.role) roleElem.textContent = profile.role;
        if (avatarElem) {
          const fetchedInitials = profile.avatar || profile.name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
          avatarElem.textContent = fetchedInitials;
        }

        // Dynamically update Welcome back banner on index.html
        const welcomeHeader = document.getElementById("welcomeUserHeader");
        if (welcomeHeader) {
          const firstName = profile.name.split(' ')[0];
          welcomeHeader.textContent = `Welcome back, ${firstName}`;
        }

        // Dynamically populate profile page fields on profile.html
        const profileNameHeader = document.querySelector("#profileForm")?.closest("div")?.querySelector("h4");
        if (profileNameHeader) profileNameHeader.textContent = profile.name;
        const profileInputs = document.querySelectorAll("#profileForm input");
        if (profileInputs.length >= 2) {
          if (profileInputs[0]) profileInputs[0].value = profile.name;
          if (profileInputs[1] && profile.email) profileInputs[1].value = profile.email;
        }
        if (profileInputs.length >= 3 && profile.department) {
          profileInputs[2].value = profile.department;
        }
      }
    }).catch(err => console.warn("Notice: could not load user profile from DB:", err));
  }
}

window.toggleEmployeeDarkMode = function(e) {
    if (e) {
        if (e.__darkToggleHandled) return;
        e.__darkToggleHandled = true;
        if (typeof e.preventDefault === 'function') e.preventDefault();
        if (typeof e.stopPropagation === 'function') e.stopPropagation();
    }
    document.body.classList.toggle("dark-mode");
    const activeDark = document.body.classList.contains("dark-mode");
    console.log("%c[Dark Mode Clicked] Active dark mode: " + activeDark, "color: #9333ea; font-weight: bold; font-size: 14px;");
    localStorage.setItem("theme", activeDark ? "dark" : "light");

    const moonSvg = document.getElementById("customMoon");
    const sunSvg = document.getElementById("customSun");
    if (moonSvg && sunSvg) {
        moonSvg.style.display = activeDark ? "none" : "inline-block";
        sunSvg.style.display = activeDark ? "inline-block" : "none";
    }

    const moonIcon = document.getElementById("moonIcon");
    const sunIcon = document.getElementById("sunIcon");
    if (moonIcon && sunIcon) {
        moonIcon.style.display = activeDark ? "none" : "inline-block";
        sunIcon.style.display = activeDark ? "inline-block" : "none";
    }
};

window.toggleEmployeeSidebar = function(e) {
    if (e) {
        if (e.__sidebarToggleHandled) return;
        e.__sidebarToggleHandled = true;
        if (typeof e.preventDefault === 'function') e.preventDefault();
        if (typeof e.stopPropagation === 'function') e.stopPropagation();
    }
    console.log("%c[Hamburger Clicked] Toggling sidebar collapse.", "color: #3b82f6; font-weight: bold; font-size: 14px;");
    document.body.classList.toggle("sidebar-collapsed");
    document.body.classList.toggle("sidebar-closed");
    
    const sidebar = document.querySelector(".sidebar") || document.getElementById("shared-sidebar");
    if (sidebar) {
        sidebar.classList.toggle("collapsed");
        console.log("[Sidebar Log] Toggled .collapsed on sidebar element.");
    }
};

// Global Event Delegation for Dark Mode and Hamburger Sidebar Toggle
document.addEventListener("click", function(e) {
    const darkBtn = e.target.closest("#myCustomDarkToggle, #darkModeToggle, .dark-mode-toggle");
    if (darkBtn) {
        window.toggleEmployeeDarkMode(e);
        return;
    }

    const sidebarBtn = e.target.closest("#sidebarToggle, #brandMenuToggle, .sidebar-toggle");
    if (sidebarBtn) {
        window.toggleEmployeeSidebar(e);
        return;
    }
});

// Run initializers
function initComponents() {
    if (window.AzureAuth && typeof window.AzureAuth.enforcePageAccessControl === "function") {
        if (!window.AzureAuth.enforcePageAccessControl()) return;
    }
    renderEmployeeNMSidebar();
    renderEmployeeNMTopNav();
    
    // Check saved theme on load
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme === "dark") {
        document.body.classList.add("dark-mode");
    }
    const activeDark = document.body.classList.contains("dark-mode");
    console.log("%c[Initial Theme] Dark mode active: " + activeDark, "color: #10b981; font-weight: bold;");

    const moonSvg = document.getElementById("customMoon");
    const sunSvg = document.getElementById("customSun");
    if (moonSvg && sunSvg) {
        moonSvg.style.display = activeDark ? "none" : "inline-block";
        sunSvg.style.display = activeDark ? "inline-block" : "none";
    }

    // Trigger backend profile fetch after DOM & scripts have loaded
    if (typeof apiFetchUserProfile === "function") {
        console.log("%c[Profile Sync] Initiating GET /api/users/profile fetch from DB...", "color: #3b82f6; font-weight: bold;");
        apiFetchUserProfile().then(profile => {
            console.log("%c[Profile Sync] Successfully received user profile from DB:", "color: #10b981; font-weight: bold;", profile);
            if (profile && profile.name) {
                const nameElem = document.getElementById("topNavUserName");
                const avatarElem = document.getElementById("topNavAvatar");
                if (nameElem) nameElem.textContent = profile.name;
                if (avatarElem) {
                    const fetchedInitials = profile.avatar || profile.name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
                    avatarElem.textContent = fetchedInitials;
                }
                const welcomeHeader = document.getElementById("welcomeUserHeader");
                if (welcomeHeader) {
                    const firstName = profile.name.split(' ')[0];
                    welcomeHeader.textContent = `Welcome back, ${firstName}`;
                }
                const profileNameHeader = document.querySelector("#profileForm")?.closest("div")?.querySelector("h4");
                if (profileNameHeader) profileNameHeader.textContent = profile.name;
                const profileInputs = document.querySelectorAll("#profileForm input");
                if (profileInputs.length >= 2) {
                    if (profileInputs[0]) profileInputs[0].value = profile.name;
                    if (profileInputs[1] && profile.email) profileInputs[1].value = profile.email;
                }
                if (profileInputs.length >= 3 && profile.department) {
                    profileInputs[2].value = profile.department;
                }
            }
        }).catch(err => console.error("❌ [Profile Sync Error] Failed to load user profile from DB:", err));
    } else {
        console.warn("⚠️ [Profile Sync Warning] apiFetchUserProfile function is NOT available on this page scope.");
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initComponents);
} else {
    initComponents();
}
