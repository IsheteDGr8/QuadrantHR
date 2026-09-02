<script>
  import StatusBadge from './StatusBadge.svelte';
  import { changeTicketStatus, selectedTicket, activeTab } from '../lib/stores/tickets.js';
  import { userStore } from '../lib/stores/auth.js';

  export let ticket;

  $: currentOid = ($userStore?.objectId || $userStore?.azure_object_id || $userStore?.oid || '').toLowerCase().trim();
  $: currentEmail = ($userStore?.email || '').toLowerCase().trim();
  $: ticketReq = (ticket?.requester_id || ticket?.user_id || '').toLowerCase().trim();
  $: isCreator = !!(ticketReq && (
    (currentOid && ticketReq === currentOid) ||
    (currentEmail && ticketReq === currentEmail)
  ));

  function selectCard() {
    $selectedTicket = ticket;
    $activeTab = 'ticket-detail';
  }

  function quickResolve(e) {
    e.stopPropagation();
    if (isCreator) return;
    changeTicketStatus(ticket.id, 'Resolved');
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events a11y-interactive-supports-focus -->
<div 
  class="ticket-card" 
  class:active={$selectedTicket?.id === ticket.id} 
  on:click={selectCard}
  role="button"
  tabindex="0"
>
  <div class="card-header">
    <div class="ticket-id">{ticket.id || 'TICK-8000'}</div>
    <div class="badges">
      <StatusBadge status={ticket.priority || 'Medium'} type="priority" />
      <StatusBadge status={ticket.status || 'Open'} type="status" />
    </div>
  </div>

  <h3 class="card-title">{ticket.title}</h3>
  
  {#if ticket.description}
    <p class="card-desc">{ticket.description}</p>
  {/if}

  <div class="card-footer">
    <div class="meta-info">
      <span class="meta-item"><i class="ph-bold ph-user"></i> {ticket.requester || ticket.department || 'Employee'}</span>
      <span class="meta-item"><i class="ph-bold ph-user-check"></i> {ticket.assigned_to || 'Unassigned'}</span>
      <span class="meta-item"><i class="ph-bold ph-tag"></i> {ticket.category || 'General'}</span>
    </div>

    {#if (ticket.status || '').toLowerCase() !== 'resolved' && !isCreator}
      <button class="btn-resolve" on:click={quickResolve} title="Quick Resolve Ticket">
        <i class="ph-bold ph-check"></i>
      </button>
    {/if}
  </div>
</div>

<style>
  .ticket-card {
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 18px;
    transition: all 0.2s ease;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  }

  .ticket-card:hover {
    border-color: #a5b4fc;
    transform: translateY(-2px);
    box-shadow: 0 8px 16px rgba(79, 70, 229, 0.08);
  }

  .ticket-card.active {
    border-color: var(--primary);
    background: #f8fafc;
    box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15);
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .ticket-id {
    font-family: monospace;
    font-weight: 700;
    font-size: 0.8rem;
    color: var(--primary);
    background: var(--primary-light);
    padding: 2px 8px;
    border-radius: 6px;
  }

  .badges {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .card-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-main);
    line-height: 1.35;
  }

  .card-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.4;
    display: -webkit-box;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 10px;
    border-top: 1px solid #f1f5f9;
    margin-top: 4px;
  }

  .meta-info {
    display: flex;
    align-items: center;
    gap: 14px;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .meta-item {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .btn-resolve {
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #a7f3d0;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-resolve:hover {
    background: #10b981;
    color: #ffffff;
  }
</style>
