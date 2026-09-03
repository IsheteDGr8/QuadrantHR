<script>
  import { activeTab, sidebarCollapsed } from '../lib/stores/tickets.js';
  import { userStore, isTicketer, isAdmin, isSuperAdmin } from '../lib/stores/auth.js';

  function toggleSidebar() {
    $sidebarCollapsed = !$sidebarCollapsed;
  }

  function setTab(tabName) {
    $activeTab = tabName;
  }

  $: userRole = ($userStore?.role || 'Employee').trim();
  $: userDept = $userStore?.department || (isSuperAdmin($userStore) ? 'Upper Executive Management' : 'IT Operations');
  $: showDeptSection = isTicketer($userStore) || isSuperAdmin($userStore);
  $: showUpperManagement = isSuperAdmin($userStore);
  $: showAdminSection = isAdmin($userStore) || isSuperAdmin($userStore);
  $: normalizedRole = ($userStore?.role || '').trim().toLowerCase();
  $: canManagePolicies = ['admin', 'super admin', 'ticketer'].includes(normalizedRole);
  $: showTicketerPolicies = canManagePolicies && !showAdminSection;
</script>

<aside class="sidebar" class:collapsed={$sidebarCollapsed}>
  <div class="sidebar-top">
    <!-- Brand Header -->
    <div class="sidebar-header">
      <div class="brand-cluster" on:click={() => $sidebarCollapsed && toggleSidebar()} on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && $sidebarCollapsed && toggleSidebar()} role="button" tabindex="0">
        <div class="bot-icon" title={$sidebarCollapsed ? 'Click to expand sidebar' : ''}>
          <i class="ph-fill ph-ticket"></i>
        </div>
        <div class="sidebar-brand-text">
          <h2>TicketGenie</h2>
          <span>{userRole} Portal</span>
        </div>
      </div>

      <button class="btn-collapse" on:click={toggleSidebar} title={$sidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}>
        <i class="ph-bold {$sidebarCollapsed ? 'ph-caret-right' : 'ph-caret-left'}"></i>
      </button>
    </div>

    <!-- Navigation List -->
    <nav class="nav-sections">
      <!-- 1. EMPLOYEE SECTION (Everyone) -->
      <div class="nav-section">
        <div class="nav-title">EMPLOYEE</div>

        <button
          class="nav-link" 
          class:active={$activeTab === 'dashboard' || $activeTab === 'my-tickets'} 
          on:click={() => setTab('dashboard')}
          title="My Tickets"
        >
          <span class="menu-icon"><i class="ph-duotone ph-ticket"></i></span>
          <span class="menu-text">My Tickets</span>
        </button>

        <button 
          class="nav-link" 
          class:active={$activeTab === 'create-ticket'} 
          on:click={() => setTab('create-ticket')}
          title="Create Ticket"
        >
          <span class="menu-icon"><i class="ph-duotone ph-plus-circle"></i></span>
          <span class="menu-text">Create Ticket</span>
        </button>

        <button 
          class="nav-link" 
          class:active={$activeTab === 'announcements'} 
          on:click={() => setTab('announcements')}
          title="Announcements"
        >
          <span class="menu-icon"><i class="ph-duotone ph-megaphone"></i></span>
          <span class="menu-text">Announcements</span>
        </button>

        <button 
          class="nav-link" 
          class:active={$activeTab === 'notifications'} 
          on:click={() => setTab('notifications')}
          title="Notifications"
        >
          <span class="menu-icon"><i class="ph-duotone ph-bell"></i></span>
          <span class="menu-text">Notifications</span>
        </button>

        <button
          class="nav-link"
          class:active={$activeTab === 'genie-ai'}
          on:click={() => setTab('genie-ai')}
          title="Genie AI"
        >
          <span class="menu-icon"><i class="ph-duotone ph-sparkle"></i></span>
          <span class="menu-text">Genie AI</span>
        </button>

        <button
          class="nav-link"
          class:active={$activeTab === 'profile'}
          on:click={() => setTab('profile')}
          title="Profile & Credentials"
        >
          <span class="menu-icon"><i class="ph-duotone ph-user-gear"></i></span>
          <span class="menu-text">Profile & Credentials</span>
        </button>
      </div>

      <!-- 2. DEPARTMENT SECTION (Assigned Dept Members / Ticketers / Admins) -->
      {#if showDeptSection}
        <div class="nav-section">
          <div class="nav-title">{userDept.toUpperCase()}</div>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'inbox'} 
            on:click={() => setTab('inbox')}
            title="Ticket Inbox"
          >
            <span class="menu-icon"><i class="ph-duotone ph-tray"></i></span>
            <span class="menu-text">Ticket Inbox</span>
          </button>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'dept-analytics'} 
            on:click={() => setTab('dept-analytics')}
            title="Dept Analytics"
          >
            <span class="menu-icon"><i class="ph-duotone ph-chart-pie-slice"></i></span>
            <span class="menu-text">Dept Analytics</span>
          </button>

          {#if showTicketerPolicies}
            <button
              class="nav-link"
              class:active={$activeTab === 'add-policies'}
              on:click={() => setTab('add-policies')}
              title="Add Policies"
            >
              <span class="menu-icon"><i class="ph-duotone ph-file-plus"></i></span>
              <span class="menu-text">Add Policies</span>
            </button>
          {/if}
        </div>
      {/if}

      <!-- 3. UPPER MANAGEMENT SECTION (Upper Management / SuperAdmin Only) -->
      {#if showUpperManagement}
        <div class="nav-section">
          <div class="nav-title">UPPER MANAGEMENT</div>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'onboarding'} 
            on:click={() => setTab('onboarding')}
            title="Onboarding Pipeline"
          >
            <span class="menu-icon"><i class="ph-duotone ph-user-plus"></i></span>
            <span class="menu-text">Onboarding Pipeline</span>
          </button>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'queue-it'} 
            on:click={() => setTab('queue-it')}
            title="IT Team Queue"
          >
            <span class="menu-icon"><i class="ph-duotone ph-desktop"></i></span>
            <span class="menu-text">IT Team Queue</span>
          </button>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'queue-hr'} 
            on:click={() => setTab('queue-hr')}
            title="HR Department Queue"
          >
            <span class="menu-icon"><i class="ph-duotone ph-users-three"></i></span>
            <span class="menu-text">HR Department Queue</span>
          </button>

          <button
            class="nav-link"
            class:active={$activeTab === 'queue-finance'}
            on:click={() => setTab('queue-finance')}
            title="Finance & Ops Queue"
          >
            <span class="menu-icon"><i class="ph-duotone ph-currency-circle-dollar"></i></span>
            <span class="menu-text">Finance & Ops Queue</span>
          </button>

        </div>
      {/if}

      <!-- 4. ADMIN SECTION (Admin / SuperAdmin Only) -->
      {#if showAdminSection}
        <div class="nav-section">
          <div class="nav-title">ADMINISTRATION</div>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'rbac' || $activeTab === 'settings'} 
            on:click={() => setTab('rbac')}
            title="Departments & RBAC"
          >
            <span class="menu-icon"><i class="ph-duotone ph-shield-check"></i></span>
            <span class="menu-text">Departments & RBAC</span>
          </button>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'admin-analytics' || $activeTab === 'analytics'} 
            on:click={() => setTab('admin-analytics')}
            title="General Analytics"
          >
            <span class="menu-icon"><i class="ph-duotone ph-chart-line-up"></i></span>
            <span class="menu-text">General Analytics</span>
          </button>

          <button 
            class="nav-link" 
            class:active={$activeTab === 'add-policies'} 
            on:click={() => setTab('add-policies')}
            title="Add Policies"
          >
            <span class="menu-icon"><i class="ph-duotone ph-file-plus"></i></span>
            <span class="menu-text">Add Policies</span>
          </button>
        </div>
      {/if}
    </nav>
  </div>

  <!-- Sidebar Footer -->
  <div class="sidebar-footer">
    <div class="system-status" title="System Status: Azure AD & FastAPI Active">
      <span class="status-dot"></span>
      <div class="status-info">
        <strong>System Status</strong>
        <small>Azure AD & FastAPI Active</small>
      </div>
    </div>
  </div>
</aside>

<style>
  .sidebar {
    position: relative !important;
    left: auto !important;
    top: auto !important;
    transform: none !important;
    width: 260px;
    height: 100vh;
    background-color: #2b1b38;
    color: #d1d5db;
    display: flex !important;
    flex-direction: column;
    justify-content: space-between;
    flex-shrink: 0 !important;
    z-index: 100;
    transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    white-space: nowrap;
    overflow-x: hidden;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.15);
    visibility: visible !important;
    opacity: 1 !important;
  }

  .sidebar.collapsed {
    width: 76px;
  }

  .sidebar-top {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
  }

  .sidebar-header {
    padding: 24px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
    transition: padding 0.25s;
  }

  .brand-cluster {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
  }

  .bot-icon {
    background: rgba(255, 255, 255, 0.1);
    color: #facc15;
    width: 38px;
    height: 38px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    flex-shrink: 0;
    transition: transform 0.2s;
  }

  .bot-icon:hover {
    transform: scale(1.05);
  }

  .sidebar-brand-text h2 {
    color: #ffffff;
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0;
    line-height: 1.2;
  }

  .sidebar-brand-text span {
    display: block;
    font-size: 0.65rem;
    color: #a5b4fc;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
  }

  .btn-collapse {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: #a5b4fc;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    flex-shrink: 0;
  }

  .btn-collapse:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
    transform: scale(1.08);
  }

  .nav-sections {
    padding: 18px 10px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    transition: padding 0.25s;
  }

  .nav-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    padding-bottom: 14px;
  }

  .nav-section:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .nav-title {
    font-size: 0.65rem;
    color: #818cf8;
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 1px;
    margin: 0 14px 6px;
    border-bottom: 1px dashed rgba(129, 140, 248, 0.25);
    padding-bottom: 4px;
    transition: opacity 0.2s;
  }

  .nav-link {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    margin: 0 4px;
    background: transparent;
    border: none;
    color: #d1d5db;
    font-size: 0.85rem;
    font-weight: 500;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    width: calc(100% - 8px);
  }

  .menu-icon {
    font-size: 1.25rem;
    flex-shrink: 0;
    display: flex;
    justify-content: center;
    width: 24px;
    color: #9ca3af;
    transition: font-size 0.2s;
  }

  .menu-text {
    font-size: 0.85rem;
  }

  .nav-link:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
  }

  .nav-link:hover .menu-icon {
    color: #a5b4fc;
  }

  .nav-link.active {
    background-color: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    font-weight: 600;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.1);
  }

  .nav-link.active .menu-icon {
    color: #a5b4fc;
  }

  .sidebar-footer {
    padding: 20px 18px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(0, 0, 0, 0.15);
    flex-shrink: 0;
    transition: padding 0.25s;
  }

  .system-status {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    flex-shrink: 0;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
  }

  .status-info strong {
    display: block;
    font-size: 0.78rem;
    color: #ffffff;
  }

  .status-info small {
    display: block;
    font-size: 0.68rem;
    color: #a5b4fc;
  }

  /* --- COLLAPSED ICON-ONLY MODE --- */
  .sidebar.collapsed .sidebar-header {
    padding: 16px 8px;
    flex-direction: column;
    gap: 12px;
    align-items: center;
    justify-content: center;
  }

  .sidebar.collapsed .sidebar-brand-text,
  .sidebar.collapsed .menu-text,
  .sidebar.collapsed .nav-title,
  .sidebar.collapsed .status-info {
    display: none !important;
  }

  .sidebar.collapsed .btn-collapse {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }

  .sidebar.collapsed .nav-sections {
    padding: 12px 6px;
    align-items: center;
  }

  .sidebar.collapsed .nav-section {
    width: 100%;
    align-items: center;
    padding-bottom: 10px;
  }

  .sidebar.collapsed .nav-link {
    width: 44px;
    height: 44px;
    padding: 0;
    margin: 3px 0;
    justify-content: center;
    border-radius: 10px;
  }

  .sidebar.collapsed .menu-icon {
    width: auto;
    font-size: 1.35rem;
    margin: 0;
  }

  .sidebar.collapsed .sidebar-footer {
    padding: 16px 10px;
    justify-content: center;
  }

  .sidebar.collapsed .system-status {
    justify-content: center;
  }
</style>
