<script>
  import { onMount } from 'svelte';
  import { checkAuthGuard, userStore, isTicketer } from '../lib/stores/auth.js';
  import { filteredTickets, searchQuery, statusFilter, priorityFilter, assigneeFilter, selectedTicket, activeTab, changeTicketStatus, assignTicketToSelf } from '../lib/stores/tickets.js';
  import StatusBadge from '../components/StatusBadge.svelte';
  import { apiExportTicketPDF } from '../lib/api.js';

  onMount(() => {
    checkAuthGuard('employee');
  });

  function openTicketChat(ticket) {
    $selectedTicket = ticket;
    $activeTab = 'ticket-detail';
  }

  function handleQuickResolve(e, ticket) {
    e.stopPropagation();
    changeTicketStatus(ticket.id, 'Resolved');
  }

  async function handleSelfAssign(e, ticket) {
    e.stopPropagation();
    try {
      await assignTicketToSelf(ticket.id);
    } catch (err) {
      alert(err.message || "Failed to assign ticket.");
    }
  }

  function getRequesterName(t) {
    if (t.is_anonymous) return 'Anonymous Employee';
    if (t.requester && t.requester !== t.department) return t.requester;
    if (t.requester_name && t.requester_name !== t.department) return t.requester_name;
    if (t.requester_id) {
      if (t.requester_id.includes('@')) {
        return t.requester_id.split('@')[0];
      }
      return t.requester_id;
    }
    return 'Employee User';
  }

  let sortColumn = 'createdAt';
  let sortDirection = 'desc'; // 'asc' | 'desc'

  function handleSort(col) {
    if (sortColumn === col) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = col;
      sortDirection = 'asc';
    }
  }

  const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };

  $: sortedTickets = [...$filteredTickets].sort((a, b) => {
    let valA = '';
    let valB = '';

    if (sortColumn === 'id') {
      valA = (a.id || '').toLowerCase();
      valB = (b.id || '').toLowerCase();
    } else if (sortColumn === 'title') {
      valA = (a.title || '').toLowerCase();
      valB = (b.title || '').toLowerCase();
    } else if (sortColumn === 'requester') {
      valA = getRequesterName(a).toLowerCase();
      valB = getRequesterName(b).toLowerCase();
    } else if (sortColumn === 'department') {
      valA = (a.department || '').toLowerCase();
      valB = (b.department || '').toLowerCase();
    } else if (sortColumn === 'assigned_to') {
      valA = (a.assigned_to || '').toLowerCase();
      valB = (b.assigned_to || '').toLowerCase();
    } else if (sortColumn === 'priority') {
      const pA = priorityOrder[a.priority] || 0;
      const pB = priorityOrder[b.priority] || 0;
      return sortDirection === 'asc' ? pA - pB : pB - pA;
    } else if (sortColumn === 'status') {
      valA = (a.status || '').toLowerCase();
      valB = (b.status || '').toLowerCase();
    } else if (sortColumn === 'createdAt') {
      valA = a.createdAt || a.date || '';
      valB = b.createdAt || b.date || '';
    } else {
      valA = (a[sortColumn] || '').toString().toLowerCase();
      valB = (b[sortColumn] || '').toString().toLowerCase();
    }

    if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
    if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  $: isEmployeeRole = $userStore?.role === 'Employee';

  $: queueTitle = $activeTab === 'queue-it' ? 'IT Department Queue'
                : $activeTab === 'queue-hr' ? 'HR Department Queue'
                : $activeTab === 'queue-finance' ? 'Finance & Operations Queue'
                : 'Triage Inbox';

  $: queueSubtitle = $activeTab === 'queue-it' ? 'Manage and resolve active IT support requests'
                   : $activeTab === 'queue-hr' ? 'Manage and resolve HR and benefits requests'
                   : $activeTab === 'queue-finance' ? 'Manage finance, accounts, and procurement requests'
                   : 'Interactive tabular view for triaging, inspecting, and opening ticket conversation threads';
</script>

<div class="inbox-view animate-fade">
  <!-- Header & Filters Bar -->
  <div class="inbox-header">
    <div>
      <h1 class="view-title">{queueTitle}</h1>
      <p class="view-subtitle">{queueSubtitle}</p>
    </div>

    <!-- Filter Control Bar -->
    <div class="filter-bar">
      <!-- In-Page Search Bar -->
      <div class="inbox-search">
        <i class="ph-bold ph-magnifying-glass search-icon"></i>
        <input 
          type="text" 
          placeholder="Search tickets by ID, title, requester..." 
          bind:value={$searchQuery}
        />
        {#if $searchQuery}
          <button class="clear-search-btn" on:click={() => $searchQuery = ''} title="Clear search">
            <i class="ph-bold ph-x"></i>
          </button>
        {/if}
      </div>

      <div class="filter-group">
        <label for="inbox-status-filter"><i class="ph-bold ph-funnel"></i> Status:</label>
        <select id="inbox-status-filter" bind:value={$statusFilter}>
          <option value="all">All Statuses</option>
          <option value="Open">Open</option>
          <option value="In Progress">In Progress</option>
          <option value="Resolved">Resolved</option>
        </select>
      </div>

      <div class="filter-group">
        <label for="inbox-priority-filter">Priority:</label>
        <select id="inbox-priority-filter" bind:value={$priorityFilter}>
          <option value="all">All Priorities</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
      </div>

      <div class="filter-group">
        <label for="inbox-assignee-filter"><i class="ph-bold ph-user-check"></i> Assignee:</label>
        <select id="inbox-assignee-filter" bind:value={$assigneeFilter}>
          <option value="all">All Assignees</option>
          <option value="unassigned">Unassigned Only</option>
          <option value="me">Assigned to Me</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Tabular Queue Container -->
  <div class="table-container">
    {#if sortedTickets.length === 0}
      <div class="empty-inbox">
        <i class="ph-duotone ph-tray"></i>
        <h3>No tickets found</h3>
        <p>No tickets match the selected filters or search criteria.</p>
      </div>
    {:else}
      <table class="tickets-table">
        <thead>
          <tr>
            <th on:click={() => handleSort('id')} class="sortable-th" title="Sort by Ticket ID">
              <div class="th-content">
                <span>Ticket ID</span>
                <span class="sort-icon">
                  {#if sortColumn === 'id'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th on:click={() => handleSort('title')} class="sortable-th" title="Sort by Title">
              <div class="th-content">
                <span>Title & Description</span>
                <span class="sort-icon">
                  {#if sortColumn === 'title'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th on:click={() => handleSort('requester')} class="sortable-th" title="Sort by Requester">
              <div class="th-content">
                <span>Requester</span>
                <span class="sort-icon">
                  {#if sortColumn === 'requester'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th on:click={() => handleSort('department')} class="sortable-th" title="Sort by Department">
              <div class="th-content">
                <span>Department</span>
                <span class="sort-icon">
                  {#if sortColumn === 'department'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th on:click={() => handleSort('assigned_to')} class="sortable-th" title="Sort by Assignee">
              <div class="th-content">
                <span>Assignee</span>
                <span class="sort-icon">
                  {#if sortColumn === 'assigned_to'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th on:click={() => handleSort('priority')} class="sortable-th" title="Sort by Priority">
              <div class="th-content">
                <span>Priority</span>
                <span class="sort-icon">
                  {#if sortColumn === 'priority'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th on:click={() => handleSort('status')} class="sortable-th" title="Sort by Status">
              <div class="th-content">
                <span>Status</span>
                <span class="sort-icon">
                  {#if sortColumn === 'status'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th on:click={() => handleSort('createdAt')} class="sortable-th" title="Sort by Creation Date">
              <div class="th-content">
                <span>Created</span>
                <span class="sort-icon">
                  {#if sortColumn === 'createdAt'}
                    <i class="ph-bold {sortDirection === 'asc' ? 'ph-caret-up' : 'ph-caret-down'} text-primary"></i>
                  {:else}
                    <i class="ph-bold ph-caret-up-down text-muted"></i>
                  {/if}
                </span>
              </div>
            </th>
            <th class="text-right">Chat / Action</th>
          </tr>
        </thead>
        <tbody>
          {#each sortedTickets as ticket}
            <!-- svelte-ignore a11y-click-events-have-key-events a11y-interactive-supports-focus -->
            <tr 
              class="ticket-row" 
              class:selected={$selectedTicket?.id === ticket.id}
              on:click={() => openTicketChat(ticket)}
              role="button"
              tabindex="0"
            >
              <td>
                <span class="id-badge">{ticket.id || 'TICK-0000'}</span>
              </td>
              <td>
                <div class="title-cell">
                  <span class="ticket-title-text">{ticket.title}</span>
                  {#if ticket.description}
                    <span class="ticket-desc-snippet">{ticket.description}</span>
                  {/if}
                </div>
              </td>
              <td>
                <div class="requester-cell">
                  <i class="ph-bold ph-user user-icon"></i>
                  <span>{getRequesterName(ticket)}</span>
                </div>
              </td>
              <td>
                <span class="category-tag dept-badge">
                  <i class="ph-bold ph-buildings"></i> {ticket.department || 'General'}
                </span>
              </td>
              <td>
                {#if ticket.assigned_to}
                  <span class="assignee-badge">
                    <i class="ph-bold ph-user-check"></i> {ticket.assigned_to}
                  </span>
                {:else}
                  <div class="unassigned-wrapper">
                    <span class="unassigned-tag">Unassigned</span>
                    {#if !isEmployeeRole}
                      <button 
                        class="btn-claim-inline"
                        on:click={(e) => handleSelfAssign(e, ticket)}
                        title="Assign ticket to me"
                      >
                        Claim
                      </button>
                    {/if}
                  </div>
                {/if}
              </td>
              <td>
                <StatusBadge status={ticket.priority || 'Medium'} type="priority" />
              </td>
              <td>
                <StatusBadge status={ticket.status || 'Open'} type="status" />
              </td>
              <td>
                <span class="date-text">
                  <i class="ph-bold ph-calendar"></i> {ticket.date || ticket.createdAt || 'Recently'}
                </span>
              </td>
              <td class="text-right">
                <div class="action-cell">
                  <button 
                    class="btn-open-chat" 
                    on:click={(e) => { e.stopPropagation(); openTicketChat(ticket); }}
                    title="Open Chat Conversation Thread"
                  >
                    <i class="ph-bold ph-chats"></i> Chat
                  </button>
                  {#if (ticket.status || '').toLowerCase() !== 'resolved'}
                    <button 
                      class="btn-quick-resolve" 
                      on:click={(e) => handleQuickResolve(e, ticket)}
                      title="Quick Resolve Ticket"
                    >
                      <i class="ph-bold ph-check"></i>
                    </button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>

<style>
  .inbox-view {
    padding: 28px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    width: 100%;
    min-height: 100%;
    box-sizing: border-box;
  }

  .inbox-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
  }

  .view-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .view-subtitle {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .filter-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
  }

  .inbox-search {
    position: relative;
    width: 280px;
    min-width: 200px;
  }

  .inbox-search .search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 0.95rem;
    pointer-events: none;
  }

  .inbox-search input {
    width: 100%;
    padding: 8px 32px 8px 36px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: #ffffff;
    font-size: 0.82rem;
    color: var(--text-main);
    transition: all 0.2s ease;
    box-sizing: border-box;
  }

  .inbox-search input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
  }

  .clear-search-btn {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 0.8rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .clear-search-btn:hover {
    color: var(--text-main);
    background: #f1f5f9;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-main);
  }

  .filter-group select {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: #ffffff;
    font-size: 0.82rem;
    color: var(--text-main);
    cursor: pointer;
  }

  .table-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 14px;
    box-shadow: var(--shadow-sm);
    overflow-x: auto;
    width: 100%;
  }

  .tickets-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 0.85rem;
  }

  .tickets-table th {
    background: #f8fafc;
    padding: 14px 18px;
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--border-color);
  }

  .sortable-th {
    cursor: pointer;
    user-select: none;
    transition: background 0.15s ease, color 0.15s ease;
  }

  .sortable-th:hover {
    background: #f1f5f9;
    color: var(--text-main);
  }

  .th-content {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .sort-icon {
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
  }

  .sort-icon .text-primary {
    color: var(--primary);
  }

  .sort-icon .text-muted {
    color: #94a3b8;
    opacity: 0.5;
  }

  .tickets-table td {
    padding: 16px 18px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
  }

  .ticket-row {
    cursor: pointer;
    transition: background 0.15s ease, transform 0.1s ease;
  }

  .ticket-row:hover {
    background: #f8fafc;
  }

  .ticket-row.selected {
    background: #f0fdf4;
  }

  .id-badge {
    font-family: monospace;
    font-weight: 700;
    font-size: 0.8rem;
    color: var(--primary);
    background: var(--primary-light);
    padding: 4px 10px;
    border-radius: 6px;
    display: inline-block;
  }

  .title-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 380px;
  }

  .ticket-title-text {
    font-weight: 700;
    color: var(--text-main);
    font-size: 0.9rem;
    line-height: 1.3;
  }

  .ticket-desc-snippet {
    font-size: 0.78rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 360px;
  }

  .requester-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    color: var(--text-main);
  }

  .user-icon {
    color: var(--text-muted);
  }

  .category-tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #475569;
    background: #f1f5f9;
    padding: 3px 9px;
    border-radius: 6px;
  }

  .category-tag.dept-badge {
    color: #1e1b4b;
    background: #e0e7ff;
    border: 1px solid #c7d2fe;
    font-weight: 700;
  }

  .date-text {
    font-size: 0.78rem;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .text-right {
    text-align: right;
  }

  .action-cell {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
  }

  .btn-open-chat {
    background: var(--primary);
    color: #ffffff;
    border: none;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.15s;
  }

  .btn-open-chat:hover {
    background: var(--primary-hover);
    transform: translateY(-1px);
  }

  .btn-quick-resolve {
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #a7f3d0;
    padding: 6px 10px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-quick-resolve:hover {
    background: #10b981;
    color: #ffffff;
  }

  .assignee-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #0369a1;
    background: #e0f2fe;
    border: 1px solid #bae6fd;
    padding: 3px 9px;
    border-radius: 6px;
  }

  .unassigned-wrapper {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }

  .unassigned-tag {
    font-size: 0.78rem;
    font-weight: 500;
    color: #64748b;
    background: #f1f5f9;
    padding: 3px 8px;
    border-radius: 6px;
  }

  .btn-claim-inline {
    background: #e0e7ff;
    color: #4338ca;
    border: 1px solid #c7d2fe;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-claim-inline:hover {
    background: #4338ca;
    color: #ffffff;
  }

  .empty-inbox {
    text-align: center;
    padding: 80px 20px;
    color: var(--text-muted);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .empty-inbox i {
    font-size: 3.5rem;
    color: #cbd5e1;
  }

  .empty-inbox h3 {
    font-size: 1.1rem;
    color: var(--text-main);
  }
</style>
