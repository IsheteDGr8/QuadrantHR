<script>
  import { onMount } from 'svelte';
  import { ticketMetrics, filteredTickets, activeTab, isCreateModalOpen, selectedTicket, loadTickets } from '../lib/stores/tickets.js';
  import { userStore } from '../lib/stores/auth.js';
  import StatusBadge from '../components/StatusBadge.svelte';
  import TicketCard from '../components/TicketCard.svelte';

  let queueFilter = 'unresolved'; // 'unresolved' | 'all' | 'resolved'

  $: unresolvedTickets = $filteredTickets.filter(t => {
    const status = (t.status || '').toLowerCase();
    return status !== 'resolved' && status !== 'closed';
  });

  $: resolvedTickets = $filteredTickets.filter(t => {
    const status = (t.status || '').toLowerCase();
    return status === 'resolved' || status === 'closed';
  });

  $: displayTickets = queueFilter === 'unresolved' 
    ? unresolvedTickets 
    : (queueFilter === 'resolved' ? resolvedTickets : $filteredTickets);

  onMount(() => {
    loadTickets();
  });
</script>

<div class="dashboard-view animate-fade">
  <div class="view-header">
    <div>
      <h1 class="view-title">Operations & Support Center</h1>
      <p class="view-subtitle">Overview of current ticket queues, SLA compliance, and AI triage status</p>
    </div>
    <div class="header-btns">
      <button class="btn-secondary" on:click={() => $activeTab = 'inbox'}>
        <i class="ph-bold ph-tray"></i> View Full Inbox
      </button>
      <button class="btn-primary" on:click={() => $activeTab = 'create-ticket'}>
        <i class="ph-bold ph-plus"></i> New Request
      </button>
    </div>
  </div>

  <!-- Metric Overview Cards -->
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-icon icon-blue"><i class="ph-duotone ph-ticket"></i></div>
      <div class="metric-data">
        <span class="metric-label">Total Active Tickets</span>
        <span class="metric-value">{$ticketMetrics.total}</span>
        <span class="metric-trend text-blue"><i class="ph-bold ph-arrow-up-right"></i> Active in Queue</span>
      </div>
    </div>

    <div class="metric-card">
      <div class="metric-icon icon-amber"><i class="ph-duotone ph-clock"></i></div>
      <div class="metric-data">
        <span class="metric-label">Open / In Progress</span>
        <span class="metric-value">{$ticketMetrics.open + $ticketMetrics.inProgress}</span>
        <span class="metric-trend text-amber">{$ticketMetrics.open} Unassigned</span>
      </div>
    </div>

    <div class="metric-card">
      <div class="metric-icon icon-emerald"><i class="ph-duotone ph-check-circle"></i></div>
      <div class="metric-data">
        <span class="metric-label">Resolved Records</span>
        <span class="metric-value">{$ticketMetrics.resolved}</span>
        <span class="metric-trend text-emerald"><i class="ph-bold ph-trend-up"></i> +12% this week</span>
      </div>
    </div>

    <div class="metric-card">
      <div class="metric-icon icon-purple"><i class="ph-duotone ph-shield-check"></i></div>
      <div class="metric-data">
        <span class="metric-label">SLA Compliance Rate</span>
        <span class="metric-value">{$ticketMetrics.slaPercent}%</span>
        <span class="metric-trend text-purple"><i class="ph-bold ph-lightning"></i> Target 95%</span>
      </div>
    </div>
  </div>

  <!-- Main Content Grid -->
  <div class="content-grid">
    <!-- Active Queue Section -->
    <div class="section-card">
      <div class="card-section-header">
        <div class="header-left">
          <h2><i class="ph-duotone ph-list-checks"></i> Priority Work Queue</h2>
          <span class="count-pill">{displayTickets.length} Items</span>
        </div>

        <div class="queue-filter-tabs">
          <button 
            class="q-tab" 
            class:active={queueFilter === 'unresolved'} 
            on:click={() => queueFilter = 'unresolved'}
          >
            Unresolved ({unresolvedTickets.length})
          </button>
          <button 
            class="q-tab" 
            class:active={queueFilter === 'all'} 
            on:click={() => queueFilter = 'all'}
          >
            All ({$filteredTickets.length})
          </button>
          <button 
            class="q-tab" 
            class:active={queueFilter === 'resolved'} 
            on:click={() => queueFilter = 'resolved'}
          >
            Resolved ({resolvedTickets.length})
          </button>
        </div>
      </div>

      <div class="tickets-wrapper">
        {#if displayTickets.length === 0}
          <div class="empty-state">
            <i class="ph-duotone ph-tray empty-icon"></i>
            <p>
              {#if queueFilter === 'unresolved'}
                No unresolved tickets in your active work queue
              {:else if queueFilter === 'resolved'}
                No resolved tickets found
              {:else}
                No active tickets match your search criteria
              {/if}
            </p>
          </div>
        {:else}
          <div class="tickets-list">
            {#each displayTickets as ticket}
              <TicketCard {ticket} />
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Right Side Widgets -->
    <div class="side-widgets">
      <!-- AI Triage Insights Widget -->
      <div class="widget-card">
        <div class="widget-header">
          <i class="ph-duotone ph-robot text-purple"></i>
          <h3>TicketGenie AI Assistant</h3>
        </div>
        <p class="widget-desc">AI Ticket Auto-Classification is operational with 94.2% accuracy across IT and HR queues.</p>
        <div class="ai-status-row">
          <span class="status-indicator"></span>
          <span>Model: <strong>Azure OpenAI GPT-5.2</strong></span>
        </div>
      </div>

      <!-- Quick Knowledge Articles -->
      <div class="widget-card">
        <div class="widget-header">
          <i class="ph-duotone ph-book-open text-blue"></i>
          <h3>Popular Solutions</h3>
        </div>
        <ul class="kb-quick-links">
          <li><a href="#kb" on:click|preventDefault={() => $activeTab = 'knowledge'}><i class="ph-bold ph-caret-right"></i> VPN Connection Troubleshooting Guide</a></li>
          <li><a href="#kb" on:click|preventDefault={() => $activeTab = 'knowledge'}><i class="ph-bold ph-caret-right"></i> Annual Leave Accrual & PTO Rollover Policy</a></li>
          <li><a href="#kb" on:click|preventDefault={() => $activeTab = 'knowledge'}><i class="ph-bold ph-caret-right"></i> Hardware Procurement & Device Refresh Schedule</a></li>
        </ul>
      </div>
    </div>
  </div>
</div>

<style>
  .dashboard-view {
    padding: 28px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    height: 100%;
    overflow-y: auto;
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
  }

  .view-header {
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

  .header-btns {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .btn-primary {
    background: var(--primary);
    color: white;
    border: none;
    padding: 10px 18px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-secondary {
    background: #ffffff;
    border: 1px solid var(--border-color);
    color: var(--text-main);
    padding: 10px 18px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 18px;
    width: 100%;
  }

  .metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: var(--shadow-sm);
    min-width: 0;
  }

  .metric-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    flex-shrink: 0;
  }

  .icon-blue { background: #eff6ff; color: #2563eb; }
  .icon-amber { background: #fffbeb; color: #d97706; }
  .icon-emerald { background: #ecfdf5; color: #059669; }
  .icon-purple { background: #f5f3ff; color: #7c3aed; }

  .metric-data {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .metric-label {
    font-size: 0.78rem;
    color: var(--text-muted);
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .metric-value {
    font-size: 1.45rem;
    font-weight: 700;
    color: var(--text-main);
    line-height: 1.2;
    margin: 2px 0;
  }

  .metric-trend {
    font-size: 0.72rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .text-blue { color: #2563eb; }
  .text-amber { color: #d97706; }
  .text-emerald { color: #059669; }
  .text-purple { color: #7c3aed; }

  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
    gap: 24px;
    width: 100%;
  }

  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
  }

  .section-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    box-shadow: var(--shadow-sm);
    min-width: 0;
  }

  .card-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .card-section-header h2 {
    font-size: 1.1rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .count-pill {
    background: #f1f5f9;
    color: #475569;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
  }

  .queue-filter-tabs {
    display: flex;
    align-items: center;
    background: #f1f5f9;
    padding: 3px;
    border-radius: 8px;
    gap: 2px;
  }

  .q-tab {
    background: transparent;
    border: none;
    padding: 5px 11px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .q-tab:hover {
    color: var(--text-main);
  }

  .q-tab.active {
    background: #ffffff;
    color: var(--primary);
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }

  .tickets-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-muted);
  }

  .empty-icon {
    font-size: 2.5rem;
    margin-bottom: 8px;
  }

  .side-widgets {
    display: flex;
    flex-direction: column;
    gap: 20px;
    min-width: 0;
  }

  .widget-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 20px;
    box-shadow: var(--shadow-sm);
    min-width: 0;
  }

  .widget-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 10px;
  }

  .widget-desc {
    font-size: 0.82rem;
    color: var(--text-muted);
    line-height: 1.45;
  }

  .ai-status-row {
    margin-top: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.78rem;
    background: #f8fafc;
    padding: 8px 12px;
    border-radius: 8px;
  }

  .status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
  }

  .kb-quick-links {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 8px;
  }

  .kb-quick-links a {
    color: var(--text-main);
    text-decoration: none;
    font-size: 0.82rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: color 0.15s;
  }

  .kb-quick-links a:hover {
    color: var(--primary);
  }
</style>
