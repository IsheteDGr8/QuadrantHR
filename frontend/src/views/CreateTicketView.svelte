<script>
  import { onMount } from 'svelte';
  import { activeTab, submitNewTicket, genieDraftStore } from '../lib/stores/tickets.js';
  import { userStore } from '../lib/stores/auth.js';
  import { apiCheckAnnouncementMatch, apiFetchUpperManagementUsers } from '../lib/api.js';

  let activeFormTab = 'standard'; // 'standard' | 'leave' | 'anonymous'

  // Backend leave categories (services/ticket_draft_service.py LEAVE_TYPES)
  // don't share exact strings with this form's <select> options - map
  // safely instead of assigning the raw category through and silently
  // leaving the <select> on its default.
  const LEAVE_CATEGORY_TO_FORM_TYPE = {
    'Paid Time Off (PTO)': 'Paid Time Off (PTO)',
    'Medical Leave': 'Sick Leave',
    'Parental Leave': 'Parental Leave',
    'Bereavement': 'Bereavement Leave',
    'Unpaid Leave': 'Unpaid Leave'
  };

  $: if ($genieDraftStore) {
    const draft = $genieDraftStore;
    if (draft.request_type === 'leave_management' || draft.request_type === 'leave') {
      activeFormTab = 'leave';
      const mappedLeaveType = draft.category && LEAVE_CATEGORY_TO_FORM_TYPE[draft.category];
      if (mappedLeaveType) leaveType = mappedLeaveType;
      if (draft.description) leaveNotes = draft.description;
      if (draft.startDate) {
        startDate = draft.startDate;
      } else if (draft.preferredDate) {
        // Backward-compat alias only, per models.chatbot.TicketDraft - a
        // draft that only ever had preferredDate set still prefills the
        // start date; endDate is never fabricated from it.
        startDate = draft.preferredDate;
      }
      if (draft.endDate) endDate = draft.endDate;
    } else if (draft.request_type === 'anonymous') {
      activeFormTab = 'anonymous';
      if (draft.description) anonymousMessage = draft.description;
      if (draft.category) anonymousCategory = draft.category;
    } else {
      activeFormTab = 'standard';
      if (draft.title || draft.subject) title = draft.title || draft.subject;
      if (draft.description) description = draft.description;
      if (draft.category) category = draft.category;
      if (draft.priority) priority = draft.priority;
    }

    // A Genie draft is a one-time prefill, not a permanent source of truth.
    // Clear the shared handoff after copying it into local form state so later
    // edits (leave type, dates, descriptions, etc.) are never overwritten by
    // another reactive render of this view.
    genieDraftStore.set(null);
  }

  // Standard Request Fields
  let title = '';
  let departmentSelect = 'Auto';
  let category = 'Auto';
  let priority = 'Medium';
  let description = '';
  let selectedStdApprover = '';

  // Leave Request Fields
  let leaveType = 'Paid Time Off (PTO)';
  let handoverLead = '';
  let startDate = '';
  let endDate = '';
  let leaveNotes = '';
  let selectedApprover = '';

  // Upper Management Users
  let upperManagementUsers = [];

  onMount(async () => {
    try {
      upperManagementUsers = await apiFetchUpperManagementUsers();
    } catch (err) {
      console.warn("Failed to load upper management users:", err);
    }
  });

  // Anonymous Request Fields
  let anonymousCategory = 'Workplace Feedback & Improvements';
  let anonymousMessage = '';

  // Common State
  let submitting = false;
  let errorMsg = '';
  let successMsg = '';
  let announcementMatch = null;
  let checkingAnnouncements = false;
  let bypassAnnouncementCheck = false;

  async function handleSubmitStandard() {
    if (!title.trim() || !description.trim()) {
      errorMsg = 'Please enter both a title and description before submitting.';
      return;
    }

    errorMsg = '';
    successMsg = '';

    if (!bypassAnnouncementCheck) {
      checkingAnnouncements = true;
      try {
        const result = await apiCheckAnnouncementMatch(title.trim(), description.trim());
        if (result.matched) {
          announcementMatch = result;
          return;
        }
      } catch (error) {
        console.warn('Announcement check unavailable:', error.message);
      } finally {
        checkingAnnouncements = false;
      }
    }

    bypassAnnouncementCheck = false;
    announcementMatch = null;
    submitting = true;

    let textCheck = `${title} ${description} ${category} ${departmentSelect}`.toLowerCase();
    let isLeave = textCheck.includes('leave') || textCheck.includes('pto') || textCheck.includes('vacation') || textCheck.includes('time off') || textCheck.includes('bereavement') || textCheck.includes('parental');

    let backendDept = null;
    if (departmentSelect !== 'Auto') {
      if (departmentSelect.includes('HR')) backendDept = 'HR Team';
      else if (departmentSelect.includes('Account')) backendDept = 'Accounting Team';
      else if (departmentSelect.includes('Upper') || departmentSelect.includes('Admin')) backendDept = 'Upper Management';
      else if (departmentSelect.includes('Workplace')) backendDept = 'Workplace Operations Team';
      else backendDept = 'IT Team';
    } else if (isLeave) {
      backendDept = 'Upper Management';
    }

    try {
      await submitNewTicket({
        title,
        description: description && description.length >= 10 ? description : `${description} (Standard Request Details)`,
        category: 'IT Support',
        priority,
        department: backendDept,
        department_override: backendDept,
        assigned_to: backendDept === 'Upper Management' ? (selectedStdApprover || null) : null,
        requester: $userStore?.name || 'Employee User',
        status: 'Open'
      });

      successMsg = '🎉 Support request submitted successfully! Redirecting to My Tickets...';
      title = '';
      description = '';
      setTimeout(() => { $activeTab = 'dashboard'; }, 1200);
    } catch (err) {
      errorMsg = err.message || 'Failed to submit ticket.';
    } finally {
      submitting = false;
    }
  }

  function submitDespiteAnnouncement() {
    bypassAnnouncementCheck = true;
    handleSubmitStandard();
  }

  async function handleSubmitLeave() {
    if (!startDate || !endDate) {
      errorMsg = 'Please select both start and end dates for your leave request.';
      return;
    }

    submitting = true;
    errorMsg = '';
    successMsg = '';

    try {
      await submitNewTicket({
        title: `Leave Request: ${leaveType}`,
        description: `Dates: ${startDate} to ${endDate}. Handover Lead: ${handoverLead || 'N/A'}. ${leaveNotes}`,
        category: 'Time Off',
        priority: 'Medium',
        department: 'Upper Management',
        department_override: 'Upper Management',
        assigned_to: selectedApprover || null,
        requester: $userStore?.name || 'Employee User',
        status: 'Open'
      });

      successMsg = '📅 Leave management request submitted! Redirecting to My Tickets...';
      leaveNotes = '';
      handoverLead = '';
      setTimeout(() => { $activeTab = 'dashboard'; }, 1200);
    } catch (err) {
      errorMsg = err.message || 'Failed to submit leave request.';
    } finally {
      submitting = false;
    }
  }

  async function handleSubmitAnonymous() {
    if (!anonymousMessage.trim()) {
      errorMsg = 'Please enter a confidential message.';
      return;
    }

    submitting = true;
    errorMsg = '';
    successMsg = '';

    try {
      await submitNewTicket({
        title: `Confidential Report: ${anonymousCategory}`,
        description: anonymousMessage,
        category: anonymousCategory,
        priority: 'High',
        department: 'Executive Governance',
        is_anonymous: true,
        requester: 'Anonymous Employee',
        status: 'Open'
      });

      successMsg = '🕵️ Anonymous report submitted confidentially! Redirecting...';
      anonymousMessage = '';
      setTimeout(() => { $activeTab = 'dashboard'; }, 1200);
    } catch (err) {
      errorMsg = err.message || 'Failed to submit anonymous report.';
    } finally {
      submitting = false;
    }
  }

  function handleCancel() {
    $activeTab = 'dashboard';
  }
</script>

<div class="create-ticket-view animate-fade">
  <div class="view-header">
    <div>
      <h1 class="view-title">Enterprise Ticketing & Routing</h1>
      <p class="view-subtitle">Select your submission classification below for direct routing to operational queues</p>
    </div>
    <button class="btn-secondary" on:click={handleCancel}>
      <i class="ph-bold ph-arrow-left"></i> Back to My Tickets
    </button>
  </div>

  {#if successMsg}
    <div class="success-banner">
      <i class="ph-bold ph-check-circle"></i> {successMsg}
    </div>
  {/if}

  {#if errorMsg}
    <div class="error-banner">
      <i class="ph-bold ph-warning-circle"></i> {errorMsg}
    </div>
  {/if}

  <div class="layout-grid">
    <!-- Main Form Box -->
    <div class="main-form-box">
      <!-- Tabs Bar -->
      <div class="tabs-header">
        <button 
          class="tab-btn" 
          class:active={activeFormTab === 'standard'} 
          on:click={() => activeFormTab = 'standard'}
        >
          <i class="ph-bold ph-file-text"></i> Standard Request
        </button>
        <button 
          class="tab-btn" 
          class:active={activeFormTab === 'leave'} 
          on:click={() => activeFormTab = 'leave'}
        >
          <i class="ph-bold ph-calendar"></i> Leave Management
        </button>
        <button 
          class="tab-btn" 
          class:active={activeFormTab === 'anonymous'} 
          on:click={() => activeFormTab = 'anonymous'}
        >
          <i class="ph-bold ph-user-secret"></i> Anonymous Report
        </button>
      </div>

      <!-- 1. Standard Request Form -->
      {#if activeFormTab === 'standard'}
        <div class="tab-pane animate-fade">
          <div class="pane-banner blue">
            <strong>When to use this request:</strong> General IT support, software/hardware access, account management, HR operational questions, or administrative requests linked to your profile.
          </div>

          <form on:submit|preventDefault={handleSubmitStandard} class="form-body">
            <div class="form-group">
              <label for="std-title">Request Title / Subject *</label>
              <input 
                id="std-title" 
                type="text" 
                placeholder="e.g. VPN Connection Issue / Account Provisioning" 
                bind:value={title} 
                on:input={() => announcementMatch = null}
                required 
              />
            </div>

            <div class="form-group">
              <label for="std-dept">Target Department Queue</label>
              <select id="std-dept" bind:value={departmentSelect}>
                <option value="Auto">✨ Auto (AI Routing & Triage)</option>
                <option value="IT & Technology">IT & Technology</option>
                <option value="HR & Workplace Operations">HR & Workplace Operations</option>
                <option value="Account Management">Account Management</option>
                <option value="Upper Management/Administration">Upper Management/Administration</option>
              </select>
              {#if departmentSelect !== 'Auto'}
                <small class="routing-note"><i class="ph-bold ph-check-circle"></i> Your selection will be used directly; AI department routing will be skipped.</small>
              {/if}
            </div>

            {#if departmentSelect.includes('Upper') || departmentSelect.includes('Admin')}
              <div class="form-group animate-fade">
                <label for="std-approver"><i class="ph-bold ph-user-check"></i> Assign Upper Management Approver</label>
                <select id="std-approver" bind:value={selectedStdApprover}>
                  <option value="">✨ Upper Management Pool (Unassigned)</option>
                  {#each upperManagementUsers as user}
                    <option value={user.name}>{user.name} ({user.role || 'Upper Management'})</option>
                  {/each}
                </select>
              </div>
            {/if}

            <div class="form-group">
              <label for="std-desc">Description & Specifications *</label>
              <textarea 
                id="std-desc" 
                rows="6" 
                placeholder="Provide complete specifications or error details..." 
                bind:value={description} 
                on:input={() => announcementMatch = null}
                required
              ></textarea>
            </div>

            {#if announcementMatch}
              <div class="announcement-notice" role="status">
                <div class="notice-icon"><i class="ph-bold ph-megaphone"></i></div>
                <div class="notice-body">
                  <strong>This issue may already be addressed</strong>
                  <p>“{announcementMatch.announcement.title}”</p>
                  <span>{announcementMatch.announcement.content}</span>
                  <div class="notice-actions">
                    <button type="button" class="notice-link" on:click={() => $activeTab = 'announcements'}>View announcement</button>
                    <button type="button" class="notice-submit" on:click={submitDespiteAnnouncement}>Submit anyway</button>
                  </div>
                </div>
              </div>
            {/if}

            <div class="form-footer">
              <button type="button" class="btn-cancel" on:click={handleCancel}>Cancel</button>
              <button type="submit" class="btn-submit blue-btn" disabled={submitting || checkingAnnouncements}>
                {#if checkingAnnouncements}
                  <i class="ph-bold ph-spinner animate-spin"></i> Checking announcements...
                {:else if submitting}
                  <i class="ph-bold ph-spinner animate-spin"></i> Submitting...
                {:else}
                  <i class="ph-bold ph-paper-plane-right"></i> Submit Standard Ticket
                {/if}
              </button>
            </div>
          </form>
        </div>
      {/if}

      <!-- 2. Leave Management Form -->
      {#if activeFormTab === 'leave'}
        <div class="tab-pane animate-fade">
          <div class="pane-banner green">
            <strong>When to use this request:</strong> Schedule Paid Time Off (PTO), sick leave, parental leave, or bereavement leave. Once approved, dates automatically sync with team calendars.<br>
            <em>Note: Will cycle through upper management for approval.</em>
          </div>

          <form on:submit|preventDefault={handleSubmitLeave} class="form-body">
            <div class="form-group">
              <span class="form-label">Assigned Department Queue</span>
              <div class="autofill-badge">
                <i class="ph-bold ph-shield-check text-success"></i> <strong>Upper Management</strong> (Autofilled for Leave & PTO Approval)
              </div>
            </div>

            <div class="form-group">
              <label for="leave-approver"><i class="ph-bold ph-user-check"></i> Assign Upper Management Approver</label>
              <select id="leave-approver" bind:value={selectedApprover}>
                <option value="">✨ Upper Management Pool (Unassigned)</option>
                {#each upperManagementUsers as user}
                  <option value={user.name}>{user.name} ({user.role || 'Upper Management'})</option>
                {/each}
              </select>
            </div>

            <div class="form-group">
              <label for="leave-type">Leave Type</label>
              <select id="leave-type" bind:value={leaveType}>
                <option value="Paid Time Off (PTO)">Paid Time Off (PTO)</option>
                <option value="Sick Leave">Sick Leave</option>
                <option value="Parental Leave">Parental Leave</option>
                <option value="Bereavement Leave">Bereavement Leave</option>
                <option value="Unpaid Leave">Unpaid Leave</option>
              </select>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="start-date">Start Date *</label>
                <input id="start-date" type="date" bind:value={startDate} required />
              </div>

              <div class="form-group">
                <label for="end-date">End Date *</label>
                <input id="end-date" type="date" bind:value={endDate} required />
              </div>
            </div>

            <div class="form-group">
              <label for="leave-notes">Reason / Handover Notes</label>
              <textarea 
                id="leave-notes" 
                rows="4" 
                placeholder="Enter details for HR & Management review..." 
                bind:value={leaveNotes}
              ></textarea>
            </div>

            <div class="form-footer">
              <button type="button" class="btn-cancel" on:click={handleCancel}>Cancel</button>
              <button type="submit" class="btn-submit green-btn" disabled={submitting}>
                {#if submitting}
                  <i class="ph-bold ph-spinner animate-spin"></i> Submitting...
                {:else}
                  <i class="ph-bold ph-calendar-check"></i> Submit Leave Request
                {/if}
              </button>
            </div>
          </form>
        </div>
      {/if}

      <!-- 3. Anonymous Form -->
      {#if activeFormTab === 'anonymous'}
        <div class="tab-pane animate-fade">
          <div class="pane-banner dark">
            <strong>When to use this request:</strong> Secure workplace feedback, ethics or compliance reporting, or sensitive suggestions where total anonymity is required.
          </div>

          <form on:submit|preventDefault={handleSubmitAnonymous} class="form-body">
            <div class="form-group">
              <label for="anon-cat">Category / Concern Area</label>
              <select id="anon-cat" bind:value={anonymousCategory}>
                <option value="Workplace Feedback & Improvements">Workplace Feedback & Improvements</option>
                <option value="Compliance & Ethics Reporting">Compliance & Ethics Reporting</option>
                <option value="Anonymous Suggestion">Anonymous Suggestion</option>
                <option value="Other Confidential Matter">Other Confidential Matter</option>
              </select>
            </div>

            <div class="form-group">
              <label for="anon-msg">Confidential Message *</label>
              <textarea 
                id="anon-msg" 
                rows="6" 
                placeholder="Provide detailed information securely and anonymously..." 
                bind:value={anonymousMessage} 
                required
              ></textarea>
            </div>

            <div class="form-footer">
              <button type="button" class="btn-cancel" on:click={handleCancel}>Cancel</button>
              <button type="submit" class="btn-submit dark-btn" disabled={submitting}>
                {#if submitting}
                  <i class="ph-bold ph-spinner animate-spin"></i> Submitting...
                {:else}
                  <i class="ph-bold ph-user-secret"></i> Submit Anonymously
                {/if}
              </button>
            </div>
          </form>
        </div>
      {/if}
    </div>

    <!-- Right Side Information Panels -->
    <div class="info-sidebar">
      <!-- Panel 1: Tips Card -->
      <div class="info-card tips-card">
        <div class="card-title">
          <i class="ph-bold ph-headset"></i> Talking to an Agent Tips
        </div>
        <ul class="tips-list">
          <li>Include clear error codes or screenshots in your active chat thread.</li>
          <li>Be specific about hardware or software version numbers.</li>
          <li>Keep your ticket reference ID handy for quick follow-ups.</li>
        </ul>
      </div>

      <!-- Panel 2: Genie AI Notice Card -->
      <div class="info-card genie-card">
        <div class="card-title">
          <i class="ph-fill ph-sparkle"></i> Genie AI Quick Routing Notice
        </div>
        <p class="notice-text">
          Submitting tickets through these forms instantly generates a live ticket thread. You can also use the <strong>"Genie AI"</strong> assistant widget in the bottom-right corner for instant answers before a human agent picks up your case.
        </p>
      </div>
    </div>
  </div>
</div>

<style>
  .create-ticket-view {
    padding: 28px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    height: 100%;
    overflow-y: auto;
  }

  .view-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .view-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .view-subtitle {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .btn-secondary {
    background: white;
    border: 1px solid var(--border-color);
    padding: 10px 16px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    transition: all 0.15s;
  }

  .btn-secondary:hover {
    border-color: var(--primary);
    color: var(--primary);
  }

  .success-banner {
    background: #ecfdf5;
    color: #059669;
    padding: 14px 18px;
    border-radius: 10px;
    border: 1px solid #a7f3d0;
    font-size: 0.88rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .error-banner {
    background: #fef2f2;
    color: #ef4444;
    padding: 14px 18px;
    border-radius: 10px;
    border: 1px solid #fca5a5;
    font-size: 0.88rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .layout-grid {
    display: grid;
    grid-template-columns: 3fr 1fr;
    gap: 24px;
    align-items: start;
  }

  .main-form-box {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-left: 4px solid #d4a359;
    border-radius: var(--border-radius);
    box-shadow: var(--shadow-sm);
    padding: 28px;
  }

  .tabs-header {
    display: flex;
    gap: 10px;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 16px;
    margin-bottom: 24px;
  }

  .tab-btn {
    padding: 10px 18px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: #f8fafc;
    color: var(--text-muted);
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.15s;
  }

  .tab-btn.active {
    background: var(--primary);
    color: white;
    border-color: var(--primary);
  }

  .pane-banner {
    padding: 14px 18px;
    border-radius: 8px;
    font-size: 0.85rem;
    line-height: 1.5;
    margin-bottom: 24px;
  }

  .pane-banner.blue {
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    color: #1e40af;
  }

  .pane-banner.green {
    background: #f0fdf4;
    border-left: 4px solid #10b981;
    color: #065f46;
  }

  .pane-banner.dark {
    background: #f8fafc;
    border-left: 4px solid #475569;
    color: #334155;
  }

  .form-body {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .routing-note {
    color: #047857;
    font-size: 0.72rem;
    line-height: 1.35;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  label, .form-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-main);
  }

  input, select, textarea {
    padding: 12px 16px;
    border-radius: 10px;
    border: 1px solid var(--border-color);
    font-size: 0.88rem;
    color: var(--text-main);
    background: #ffffff;
  }

  input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--primary);
  }

  .autofill-badge {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    color: #047857;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .form-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 12px;
    padding-top: 20px;
    border-top: 1px solid var(--border-color);
  }

  .btn-cancel {
    padding: 10px 20px;
    border-radius: 10px;
    border: 1px solid var(--border-color);
    background: white;
    color: var(--text-muted);
    font-weight: 600;
    cursor: pointer;
  }

  .btn-submit {
    padding: 11px 24px;
    border-radius: 10px;
    border: none;
    color: white;
    font-weight: 600;
    font-size: 0.88rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .blue-btn { background: #3b82f6; }
  .blue-btn:hover { background: #2563eb; }

  .green-btn { background: #10b981; }
  .green-btn:hover { background: #059669; }

  .dark-btn { background: #475569; }
  .dark-btn:hover { background: #334155; }

  .announcement-notice {
    display: flex;
    gap: 12px;
    padding: 16px;
    border: 1px solid #fbbf24;
    border-radius: 12px;
    background: #fffbeb;
    color: #78350f;
  }

  .notice-icon { font-size: 1.25rem; color: #d97706; }
  .notice-body { flex: 1; }
  .notice-body strong { font-size: 0.9rem; }
  .notice-body p { margin: 4px 0; font-weight: 700; color: #92400e; }
  .notice-body span { display: block; font-size: 0.8rem; line-height: 1.45; color: #78350f; }
  .notice-actions { display: flex; gap: 9px; margin-top: 12px; }
  .notice-actions button { border-radius: 8px; padding: 7px 11px; font-size: 0.78rem; font-weight: 700; cursor: pointer; }
  .notice-link { border: 1px solid #f59e0b; background: white; color: #92400e; }
  .notice-submit { border: 0; background: #d97706; color: white; }

  .info-sidebar {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .info-card {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 24px;
    box-shadow: var(--shadow-sm);
  }

  .tips-card { border-left: 4px solid #3b82f6; }
  .genie-card { border-left: 4px solid #10b981; }

  .card-title {
    font-size: 0.95rem;
    font-weight: 700;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .tips-card .card-title { color: #1e40af; }
  .genie-card .card-title { color: #065f46; }

  .tips-list {
    margin: 0;
    padding-left: 18px;
    font-size: 0.82rem;
    color: var(--text-main);
    line-height: 1.6;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .notice-text {
    margin: 0;
    font-size: 0.82rem;
    color: var(--text-main);
    line-height: 1.6;
  }
</style>
