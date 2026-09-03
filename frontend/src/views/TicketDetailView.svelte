<script>
  import { selectedTicket, activeTab, previousTab, changeTicketStatus, transferTicketDepartment, assignTicketToSelf, unassignTicket } from '../lib/stores/tickets.js';
  import { userStore, isTicketer } from '../lib/stores/auth.js';
  import StatusBadge from '../components/StatusBadge.svelte';
  import { apiFetchComments, apiPostComment, apiSuggestResponse, apiExportTicketPDF } from '../lib/api.js';

  let comments = [];
  let loadingComments = false;
  let replyMessage = '';
  let sendingReply = false;
  let generatingAiResponse = false;
  let aiSuggestedActions = [];
  let aiSafetyNoticeRequired = false;
  let showingAiGuidance = false;
  let targetTransferDept = '';
  let transferring = false;
  let assigning = false;
  let errorMsg = '';
  let commentsTicketId = null;

  $: if (ticket && ticket.department && !targetTransferDept) {
    targetTransferDept = ticket.department;
  }

  $: currentUserName = $userStore?.name || $userStore?.email?.split('@')[0] || '';
  $: currentUserEmail = ($userStore?.email || '').toLowerCase().trim();
  $: currentUserOid = ($userStore?.objectId || $userStore?.azure_object_id || $userStore?.oid || '').toLowerCase().trim();

  $: isAssignedToCurrent = (() => {
    if (!ticket || !ticket.assigned_to) return false;
    const a = ticket.assigned_to.toLowerCase().trim();
    return (currentUserName && a.includes(currentUserName.toLowerCase())) ||
           (currentUserEmail && a.includes(currentUserEmail)) ||
           (currentUserOid && a.includes(currentUserOid));
  })();

  async function handleSelfAssignDetail() {
    if (!ticket) return;
    assigning = true;
    try {
      const updated = await assignTicketToSelf(ticket.id);
      if (updated) {
        ticket = { ...ticket, assigned_to: updated.assigned_to };
        $selectedTicket = ticket;
        await loadComments();
      }
    } catch (err) {
      alert(err.message || "Failed to self-assign ticket.");
    } finally {
      assigning = false;
    }
  }

  async function handleUnassignDetail() {
    if (!ticket) return;
    assigning = true;
    try {
      const updated = await unassignTicket(ticket.id);
      if (updated) {
        ticket = { ...ticket, assigned_to: null };
        $selectedTicket = ticket;
        await loadComments();
      }
    } catch (err) {
      alert(err.message || "Failed to unassign ticket.");
    } finally {
      assigning = false;
    }
  }

  async function handleTransferTicket() {
    if (!ticket || !targetTransferDept || targetTransferDept === ticket.department) return;
    transferring = true;
    try {
      const updated = await transferTicketDepartment(ticket.id, targetTransferDept);
      if (updated) {
        ticket = { ...ticket, department: targetTransferDept };
        $selectedTicket = ticket;
        const targetTab = targetTransferDept.includes('IT') ? 'queue-it'
                        : targetTransferDept.includes('HR') ? 'queue-hr'
                        : (targetTransferDept.includes('Account') || targetTransferDept.includes('Fin')) ? 'queue-finance'
                        : 'inbox';
        $activeTab = targetTab;
      }
    } catch (err) {
      console.error("Failed to transfer ticket:", err);
      alert(err.message || "Failed to transfer ticket");
    } finally {
      transferring = false;
    }
  }

  async function handleAutoGenerateResponse() {
    if (!ticket || !ticket.id) return;
    generatingAiResponse = true;
    showingAiGuidance = false;
    try {
      const res = await apiSuggestResponse(ticket.id);
      if (res && (res.message || res.suggested_response || res.reply)) {
        replyMessage = res.message || res.suggested_response || res.reply;
        aiSuggestedActions = Array.isArray(res.suggested_actions) ? res.suggested_actions : [];
        aiSafetyNoticeRequired = Boolean(res.safety_notice_required);
        showingAiGuidance = true;
      }
    } catch (err) {
      console.error("Failed to generate AI response:", err);
      alert(err.message || "Failed to generate AI response");
    } finally {
      generatingAiResponse = false;
    }
  }

  function isRawGuid(str) {
    return str && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);
  }

  function getSenderDisplayName(c) {
    // If backend resolved a real name (not a GUID), use it
    if (c.sender_name && !isRawGuid(c.sender_name)) return c.sender_name;
    if (c.sender && !isRawGuid(c.sender) && !c.sender.includes('-')) return c.sender;

    // Check if it's the currently logged-in user
    const sId = c.sender_id || '';
    if (sId && $userStore && (sId === $userStore.objectId || sId === $userStore.azure_object_id || sId === $userStore.oid)) {
      return $userStore.name || $userStore.email?.split('@')[0] || 'Employee';
    }

    // Email address — use prefix
    if (sId.includes('@')) return sId.split('@')[0];

    // Raw GUID or anything unresolvable — show clean role-based label
    const role = c.sender_role || '';
    if (role === 'Support' || role === 'Admin' || role === 'Ticketer') return 'Support Agent';
    return 'Employee';
  }

  $: ticket = $selectedTicket;

  $: requesterDisplayName = (() => {
    if (!ticket) return 'Employee';
    const rid = ticket.requester_id || '';
    // If the requester is the currently logged-in user, use their known name
    if ($userStore && rid && (
      rid === $userStore.oid ||
      rid === $userStore.objectId ||
      rid === $userStore.azure_object_id
    )) {
      return $userStore.name || $userStore.email?.split('@')[0] || 'Employee';
    }
    // Use backend-resolved name if it's not a raw GUID
    if (ticket.requester_name && !isRawGuid(ticket.requester_name)) {
      return ticket.requester_name;
    }
    return 'Employee';
  })();

  $: backLabel = $previousTab === 'inbox' ? 'Triage Inbox'
               : $previousTab === 'queue-it' ? 'IT Queue'
               : $previousTab === 'queue-hr' ? 'HR Queue'
               : $previousTab === 'queue-finance' ? 'Finance Queue'
               : $previousTab === 'dashboard' || $previousTab === 'my-tickets' ? 'My Tickets'
               : 'Previous View';

  $: classificationReason = ticket?.classification_reason || ticket?.reason || '';
  $: isManualDepartmentRouting = classificationReason.startsWith('User-selected department override');
  $: systemAiMessage = classificationReason ? {
    sender_id: 'AI Genie',
    sender_role: 'System',
    message: isManualDepartmentRouting
      ? `Manual Department Routing: ${classificationReason}`
      : `AI Auto-Classification (${Math.round((ticket.classification_confidence || ticket.confidence || 0.94) * 100)}% confidence): ${classificationReason}`,
    createdAt: 'Auto-Triaged'
  } : null;

  $: currentOid = ($userStore?.objectId || $userStore?.azure_object_id || $userStore?.oid || '').toLowerCase().trim();
  $: currentEmail = ($userStore?.email || '').toLowerCase().trim();
  $: ticketReq = (ticket?.requester_id || ticket?.user_id || '').toLowerCase().trim();
  $: isCreator = !!(ticketReq && (
    (currentOid && ticketReq === currentOid) ||
    (currentEmail && ticketReq === currentEmail)
  ));

  $: displayComments = systemAiMessage 
    ? [systemAiMessage, ...comments.filter(c => c.sender_role !== 'System')] 
    : comments;

  $: if (ticket?.id && ticket.id !== commentsTicketId) {
    commentsTicketId = ticket.id;
    loadComments();
  }

  async function loadComments() {
    if (!ticket || !ticket.id) return;
    loadingComments = true;
    try {
      const fetched = await apiFetchComments(ticket.id);
      if (Array.isArray(fetched)) {
        comments = fetched;
      }
    } catch (err) {
      console.warn("Failed to load comments:", err);
    } finally {
      loadingComments = false;
    }
  }

  async function handleSendReply() {
    if (!replyMessage.trim() || !ticket) return;
    sendingReply = true;
    errorMsg = '';
    const text = replyMessage.trim();

    try {
      const createdComment = await apiPostComment(ticket.id, text);
      replyMessage = '';
      aiSuggestedActions = [];
      aiSafetyNoticeRequired = false;
      showingAiGuidance = false;
      if (createdComment && createdComment.id) {
        comments = [...comments, createdComment];
      } else {
        comments = [
          ...comments,
          {
            sender_id: $userStore?.name || 'User',
            sender_role: $userStore?.role || 'Employee',
            message: text,
            createdAt: 'Just now'
          }
        ];
      }
    } catch (err) {
      console.error("Failed to post comment:", err);
      // Fallback local update
      comments = [
        ...comments,
        {
          sender_id: $userStore?.name || 'User',
          sender_role: $userStore?.role || 'Employee',
          message: text,
          createdAt: 'Just now'
        }
      ];
      replyMessage = '';
    } finally {
      sendingReply = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendReply();
    }
  }

  function goBack() {
    $activeTab = $previousTab || 'dashboard';
  }

  function downloadDocx(ticketId) {
    if (!ticketId) return;
    window.open(`/api/tickets/${encodeURIComponent(ticketId)}/export?format=docx`, '_blank');
  }

  function handleStatusChange(newStatus) {
    if (ticket) {
      changeTicketStatus(ticket.id, newStatus);
      ticket = { ...ticket, status: newStatus };
      $selectedTicket = ticket;
    }
  }
</script>

<div class="ticket-detail-page animate-fade">
  <!-- Back Button & Page Header -->
  <div class="detail-nav-header">
    <button class="btn-back" on:click={goBack}>
      <i class="ph-bold ph-arrow-left"></i> Back to {backLabel}
    </button>
  </div>

  {#if !ticket}
    <div class="empty-state-card">
      <i class="ph-duotone ph-ticket empty-icon"></i>
      <h2>No Ticket Selected</h2>
      <p>Please select a ticket from your dashboard or requests list to view details.</p>
      <button class="btn-primary" on:click={goBack}>Return to Dashboard</button>
    </div>
  {:else}
    <div class="detail-layout">
      <!-- Top Card: Ticket Summary & Metadata -->
      <div class="summary-card">
        <div class="card-header-row">
          <div>
            <div class="id-badge">#{ticket.id}</div>
            <h1 class="ticket-title">{ticket.title}</h1>
          </div>

          <div class="export-actions">
            <button class="btn-export pdf" on:click={() => apiExportTicketPDF(ticket.id)}>
              <i class="ph-bold ph-file-pdf"></i> Export PDF
            </button>
          </div>
        </div>

        <div class="meta-strip">
          <div class="meta-item">
            <span class="meta-label">Category</span>
            <span class="meta-val"><i class="ph-bold ph-tag"></i> {ticket.category || 'General'}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Department</span>
            <span class="meta-val"><i class="ph-bold ph-buildings"></i> {ticket.department || 'Unassigned'}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Assignee</span>
            <span class="meta-val"><i class="ph-bold ph-user-check"></i> {ticket.assigned_to || 'Unassigned'}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Priority</span>
            <StatusBadge status={ticket.priority || 'Medium'} type="priority" />
          </div>
          <div class="meta-item">
            <span class="meta-label">Status</span>
            <StatusBadge status={ticket.status || 'Open'} type="status" />
          </div>
          <div class="meta-item">
            <span class="meta-label">Created Date</span>
            <span class="meta-val"><i class="ph-bold ph-calendar"></i> {ticket.date || ticket.createdAt || 'Today'}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Submitted By</span>
            <span class="meta-val"><i class="ph-bold ph-user"></i> {requesterDisplayName}</span>
          </div>
        </div>

        <div class="description-section">
          <h3><i class="ph-bold ph-align-left"></i> Issue Description</h3>
          <p class="desc-body">{ticket.description || 'No additional description provided.'}</p>
        </div>

        {#if isTicketer($userStore)}
          <!-- Assignee Action Bar -->
          <div class="assignee-change-bar">
            <span class="assignee-bar-title"><i class="ph-bold ph-user-check"></i> Ticket Assignee:</span>
            <span class="current-assignee-text">{ticket.assigned_to ? ticket.assigned_to : 'Unassigned'}</span>
            {#if !isAssignedToCurrent}
              <button 
                class="btn-assign-me" 
                on:click={handleSelfAssignDetail}
                disabled={assigning}
              >
                {#if assigning}
                  <i class="ph-bold ph-spinner animate-spin"></i> Assigning...
                {:else}
                  <i class="ph-bold ph-user-plus"></i> Assign to Me
                {/if}
              </button>
            {:else}
              <button 
                class="btn-unassign-me" 
                on:click={handleUnassignDetail}
                disabled={assigning}
              >
                {#if assigning}
                  <i class="ph-bold ph-spinner animate-spin"></i> Updating...
                {:else}
                  <i class="ph-bold ph-user-minus"></i> Unassign Ticket
                {/if}
              </button>
            {/if}
          </div>

          <div class="status-change-bar">
            <span>Update Ticket Status:</span>
            <button 
              class="btn-status open" 
              class:active={ticket.status === 'Open'} 
              on:click={() => handleStatusChange('Open')}
            >
              Open
            </button>
            <button 
              class="btn-status progress" 
              class:active={ticket.status === 'In Progress'} 
              on:click={() => handleStatusChange('In Progress')}
            >
              In Progress
            </button>
            {#if !isCreator}
              <button 
                class="btn-status resolve" 
                class:active={ticket.status === 'Resolved'} 
                on:click={() => handleStatusChange('Resolved')}
              >
                Resolved
              </button>
            {/if}
          </div>

          <!-- Transfer & Re-route Bar -->
          <div class="transfer-change-bar">
            <span class="transfer-title"><i class="ph-bold ph-arrows-left-right"></i> Transfer / Re-route:</span>
            <select class="transfer-select" bind:value={targetTransferDept}>
              <option value="IT Team">IT Team Queue</option>
              <option value="HR Team">HR Team Queue</option>
              <option value="Accounting">Finance & Ops Queue</option>
              <option value="Upper Executive Management">Upper Management Queue</option>
            </select>
            <button 
              class="btn-transfer" 
              on:click={handleTransferTicket}
              disabled={transferring || !targetTransferDept || targetTransferDept === ticket.department}
            >
              {#if transferring}
                <i class="ph-bold ph-spinner animate-spin"></i> Transferring...
              {:else}
                <i class="ph-bold ph-paper-plane-tilt"></i> Transfer & Re-route
              {/if}
            </button>
          </div>
        {/if}
      </div>

      <!-- Bottom Card: Support Conversation Thread -->
      <div class="thread-card">
        <div class="thread-header">
          <h2><i class="ph-duotone ph-chats text-primary"></i> Support Conversation Thread ({displayComments.length})</h2>
          <p>Direct communication channel with IT, HR, and Support Agents</p>
        </div>

        <div class="thread-messages-list">
          {#if loadingComments}
            <div class="loading-state">
              <i class="ph-bold ph-spinner animate-spin"></i> Loading conversation thread...
            </div>
          {:else if displayComments.length === 0}
            <div class="empty-thread">
              <i class="ph-duotone ph-chat-circle-dots"></i>
              <p>No messages yet in this conversation thread.</p>
            </div>
          {:else}
            {#each displayComments as c}
              <div 
                class="message-bubble" 
                class:user-bubble={c.sender_role === 'Employee' || c.sender_role === 'Requester'} 
                class:support-bubble={c.sender_role !== 'Employee' && c.sender_role !== 'Requester' && c.sender_role !== 'System'}
                class:system-bubble={c.sender_role === 'System'}
              >
                <div class="bubble-header">
                  <span class="sender-name">
                    {getSenderDisplayName(c)} 
                    <span class="role-tag">({c.sender_role || 'Employee'})</span>
                  </span>
                  <span class="msg-time">{c.createdAt || c.time || 'Recently'}</span>
                </div>
                <div class="bubble-text">{c.message || c.text || ''}</div>
              </div>
            {/each}
          {/if}
        </div>

        <div class="reply-box">
          <div class="reply-header">
            <span class="reply-label">Add Response</span>
            {#if isTicketer($userStore)}
              <button 
                class="btn-ai-suggest" 
                on:click={handleAutoGenerateResponse}
                disabled={generatingAiResponse}
                title="Auto generate an AI suggested response for this ticket"
              >
                {#if generatingAiResponse}
                  <i class="ph-bold ph-spinner animate-spin"></i> Generating Response...
                {:else}
                  <i class="ph-bold ph-sparkle"></i> Suggest reply (AI)
                {/if}
              </button>
            {/if}
          </div>
          <textarea 
            class="reply-textarea" 
            placeholder="Type your message or response to support (Cmd+Enter / Ctrl+Enter to send)..." 
            bind:value={replyMessage}
            on:keydown={handleKeydown}
            rows="4"
          ></textarea>
          {#if showingAiGuidance}
            <div class="ai-guidance" role="status">
              <div class="ai-guidance-heading">
                <i class="ph-fill ph-sparkle"></i>
                <strong>AI-generated draft — review before sending</strong>
              </div>
              {#if aiSuggestedActions.length > 0}
                <div class="ai-next-steps">
                  <strong>What to do next</strong>
                  <ul>
                    {#each aiSuggestedActions as action}
                      <li>{action}</li>
                    {/each}
                  </ul>
                </div>
              {/if}
              {#if aiSafetyNoticeRequired}
                <div class="ai-safety-notice">
                  <i class="ph-bold ph-warning-circle"></i>
                  <span><strong>Sensitive case:</strong> verify the wording and any escalation requirements before sending.</span>
                </div>
              {/if}
            </div>
          {/if}
          <div class="reply-actions">
            <button class="btn-send" on:click={handleSendReply} disabled={sendingReply || !replyMessage.trim()}>
              {#if sendingReply}
                <i class="ph-bold ph-spinner animate-spin"></i> Sending...
              {:else}
                <i class="ph-bold ph-paper-plane-right"></i> Send Message
              {/if}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .ticket-detail-page {
    padding: 28px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    height: 100%;
    overflow-y: auto;
    width: 100%;
    box-sizing: border-box;
  }

  .detail-nav-header {
    display: flex;
    align-items: center;
  }

  .btn-back {
    background: #ffffff;
    border: 1px solid var(--border-color);
    padding: 10px 18px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--text-main);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.15s;
  }

  .ai-guidance {
    margin-top: 10px;
    padding: 14px 16px;
    border: 1px solid #ddd6fe;
    border-left: 4px solid #7c3aed;
    border-radius: 10px;
    background: #f5f3ff;
    color: #4c1d95;
    font-size: 0.82rem;
    line-height: 1.5;
  }

  .ai-guidance-heading {
    display: flex;
    align-items: center;
    gap: 7px;
  }

  .ai-next-steps {
    margin-top: 10px;
  }

  .ai-next-steps ul {
    margin: 6px 0 0 20px;
    padding: 0;
  }

  .ai-next-steps li + li {
    margin-top: 4px;
  }

  .ai-safety-notice {
    display: flex;
    align-items: flex-start;
    gap: 7px;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #ddd6fe;
    color: #9f1239;
  }

  .btn-back:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: #f8fafc;
  }

  .empty-state-card {
    background: white;
    border-radius: 16px;
    padding: 60px 20px;
    text-align: center;
    border: 1px solid var(--border-color);
    color: var(--text-muted);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  .empty-icon {
    font-size: 3.5rem;
    color: #cbd5e1;
  }

  .detail-layout {
    display: flex;
    flex-direction: column;
    gap: 24px;
    max-width: 960px;
    width: 100%;
  }

  .summary-card, .thread-card {
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 28px;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .card-header-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
  }

  .id-badge {
    font-family: monospace;
    font-weight: 700;
    font-size: 0.85rem;
    color: var(--primary);
    background: var(--primary-light);
    padding: 4px 10px;
    border-radius: 6px;
    display: inline-block;
    margin-bottom: 6px;
  }

  .ticket-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .export-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-export {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: #ffffff;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.15s;
  }

  .btn-export.pdf { color: #dc2626; border-color: #fca5a5; background: #fef2f2; }
  .btn-export.pdf:hover { background: #dc2626; color: white; }

  .meta-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    background: #f8fafc;
    padding: 16px 20px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
  }

  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .meta-label {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
  }

  .meta-val {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .description-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 8px;
    border-top: 1px solid #f1f5f9;
  }

  .description-section h3 {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .desc-body {
    font-size: 0.9rem;
    color: var(--text-main);
    line-height: 1.6;
    background: #ffffff;
    white-space: pre-wrap;
  }

  .status-change-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: 14px;
    border-top: 1px solid #f1f5f9;
    font-size: 0.85rem;
    font-weight: 600;
  }

  .btn-status {
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid var(--border-color);
    background: #ffffff;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-status.open.active { background: #eff6ff; color: #2563eb; border-color: #bfdbfe; }
  .btn-status.progress.active { background: #fffbeb; color: #d97706; border-color: #fde68a; }
  .btn-status.resolve.active { background: #ecfdf5; color: #059669; border-color: #a7f3d0; }

  .thread-header h2 {
    font-size: 1.15rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--text-main);
  }

  .thread-header p {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .thread-messages-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-height: 420px;
    overflow-y: auto;
    padding-right: 6px;
    margin: 10px 0;
  }

  .message-bubble {
    background: #f8fafc;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .message-bubble.user-bubble {
    background: #f0fdf4;
    border-color: #bbf7d0;
  }

  .message-bubble.support-bubble {
    background: #eff6ff;
    border-color: #bfdbfe;
  }

  .message-bubble.system-bubble {
    background: #f5f3ff;
    border-color: #ddd6fe;
  }

  .bubble-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.8rem;
  }

  .sender-name {
    font-weight: 700;
    color: var(--text-main);
  }

  .role-tag {
    font-weight: 500;
    color: var(--text-muted);
  }

  .msg-time {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .bubble-text {
    font-size: 0.88rem;
    color: var(--text-main);
    line-height: 1.5;
  }

  .reply-box {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }

  .reply-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .reply-label {
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .reply-textarea {
    width: 100%;
    border: 1.5px solid #d1d5db;
    border-radius: 8px;
    min-height: 155px;
    padding: 16px;
    font-size: 0.9rem;
    line-height: 1.5;
    outline: none;
    font-family: inherit;
    resize: vertical;
    transition: 0.2s;
    box-sizing: border-box;
    color: var(--text-main);
    background: #ffffff;
  }

  .reply-textarea:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3.5px rgba(99, 102, 241, 0.12);
  }

  .reply-actions {
    display: flex;
    justify-content: flex-end;
  }

  .btn-send {
    padding: 10px 22px;
    border-radius: 8px;
    border: none;
    background: var(--primary);
    color: #ffffff;
    font-weight: 600;
    font-size: 0.88rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-send:hover {
    background: var(--primary-hover);
  }

  .btn-send:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-ai-suggest {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #ffffff;
    border: none;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
    box-shadow: 0 2px 6px rgba(99, 102, 241, 0.25);
  }

  .btn-ai-suggest:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
  }

  .btn-ai-suggest:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .transfer-change-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px dashed var(--border-color);
  }

  .transfer-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .transfer-select {
    padding: 7px 12px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-main);
    background: #ffffff;
    outline: none;
    cursor: pointer;
  }

  .transfer-select:focus {
    border-color: var(--primary);
  }

  .btn-transfer {
    background: #0284c7;
    color: #ffffff;
    border: none;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 0.2s;
  }

  .btn-transfer:hover:not(:disabled) {
    background: #0369a1;
  }

  .btn-transfer:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .assignee-change-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px dashed var(--border-color);
  }

  .assignee-bar-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .current-assignee-text {
    font-size: 0.85rem;
    font-weight: 600;
    color: #0369a1;
    background: #e0f2fe;
    padding: 3px 10px;
    border-radius: 6px;
    border: 1px solid #bae6fd;
  }

  .btn-assign-me {
    background: #4338ca;
    color: #ffffff;
    border: none;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 0.2s, transform 0.1s;
  }

  .btn-assign-me:hover:not(:disabled) {
    background: #3730a3;
    transform: translateY(-1px);
  }

  .btn-assign-me:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-unassign-me {
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }

  .btn-unassign-me:hover:not(:disabled) {
    background: #e2e8f0;
    color: #1e293b;
  }

  .btn-unassign-me:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
