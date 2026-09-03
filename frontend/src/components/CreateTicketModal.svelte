<script>
  import { onMount } from 'svelte';
  import { activeTab, isCreateModalOpen, submitNewTicket } from '../lib/stores/tickets.js';
  import { userStore } from '../lib/stores/auth.js';
  import { apiCheckAnnouncementMatch, apiFetchUpperManagementUsers } from '../lib/api.js';

  let title = '';
  let departmentSelect = 'Auto';
  let category = 'Auto';
  let priority = 'Medium';
  let description = '';
  let selectedApprover = '';
  let upperManagementUsers = [];
  let submitting = false;
  let errorMsg = '';
  let announcementMatch = null;
  let checkingAnnouncements = false;
  let bypassAnnouncementCheck = false;

  onMount(async () => {
    try {
      upperManagementUsers = await apiFetchUpperManagementUsers();
    } catch (err) {
      console.warn("Failed to fetch upper management users:", err);
    }
  });

  async function handleSubmit() {
    if (!title.trim()) {
      errorMsg = 'Please enter a ticket title.';
      return;
    }

    errorMsg = '';
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
    let textCheck = `${title} ${description} ${departmentSelect}`.toLowerCase();
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
        description: description && description.length >= 10 ? description : `${description || title} (Submitted via Quick Modal)`,
        category: 'IT Support',
        priority,
        department: backendDept,
        department_override: backendDept,
        assigned_to: backendDept === 'Upper Management' ? (selectedApprover || null) : null,
        requester: $userStore?.name || 'Employee User',
        status: 'Open'
      });
      $isCreateModalOpen = false;
      title = '';
      description = '';
      selectedApprover = '';
    } catch (err) {
      errorMsg = err.message || 'Failed to submit ticket.';
    } finally {
      submitting = false;
    }
  }

  function closeModal() {
    $isCreateModalOpen = false;
    announcementMatch = null;
  }

  function submitDespiteAnnouncement() {
    bypassAnnouncementCheck = true;
    handleSubmit();
  }

  function viewAnnouncement() {
    $isCreateModalOpen = false;
    $activeTab = 'announcements';
    announcementMatch = null;
  }
</script>

{#if $isCreateModalOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
  <div class="modal-backdrop animate-fade" on:click={closeModal} role="presentation">
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
    <div class="modal-card" on:click|stopPropagation role="dialog" aria-modal="true">
      <div class="modal-header">
        <div class="title-group">
          <div class="modal-icon">
            <i class="ph-bold ph-plus-circle"></i>
          </div>
          <div>
            <h2>Create New Support Ticket</h2>
            <p>Log a request for IT, HR, Legal, or Operations support</p>
          </div>
        </div>
        <button class="close-btn" on:click={closeModal}>
          <i class="ph-bold ph-x"></i>
        </button>
      </div>

      {#if errorMsg}
        <div class="error-banner">
          <i class="ph-bold ph-warning-circle"></i> {errorMsg}
        </div>
      {/if}

      <form on:submit|preventDefault={handleSubmit} class="modal-body">
        <div class="form-group">
          <label for="ticket-title">Issue Title / Subject *</label>
          <input 
            id="ticket-title" 
            type="text" 
            placeholder="e.g. VPN Access Token Renewal Failed" 
            bind:value={title} 
            on:input={() => announcementMatch = null}
            required 
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="ticket-dept">Department Queue</label>
            <select id="ticket-dept" bind:value={departmentSelect}>
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

          <div class="form-group">
            <label for="ticket-priority">Priority</label>
            <select id="ticket-priority" bind:value={priority}>
              <option value="Low">Low (General Query)</option>
              <option value="Medium">Medium (Standard Request)</option>
              <option value="High">High (Urgent Work Blocker)</option>
            </select>
          </div>
        </div>

        {#if departmentSelect.includes('Upper') || departmentSelect.includes('Admin')}
          <div class="form-group animate-fade">
            <label for="modal-approver"><i class="ph-bold ph-user-check"></i> Assign Upper Management Approver</label>
            <select id="modal-approver" bind:value={selectedApprover}>
              <option value="">✨ Upper Management Pool (Unassigned)</option>
              {#each upperManagementUsers as user}
                <option value={user.name}>{user.name} ({user.role || 'Upper Management'})</option>
              {/each}
            </select>
          </div>
        {/if}

        <div class="form-group">
          <label for="ticket-desc">Description & Details</label>
          <textarea 
            id="ticket-desc" 
            rows="4" 
            placeholder="Provide specific details, error codes, or steps to reproduce..." 
            bind:value={description}
            on:input={() => announcementMatch = null}
          ></textarea>
        </div>

        {#if announcementMatch}
          <div class="announcement-notice" role="status">
            <i class="ph-bold ph-megaphone"></i>
            <div>
              <strong>This issue may already be addressed</strong>
              <p>“{announcementMatch.announcement.title}”</p>
              <span>{announcementMatch.announcement.content}</span>
              <div class="notice-actions">
                <button type="button" class="notice-link" on:click={viewAnnouncement}>View announcement</button>
                <button type="button" class="notice-submit" on:click={submitDespiteAnnouncement}>Submit anyway</button>
              </div>
            </div>
          </div>
        {/if}

        <div class="modal-footer">
          <button type="button" class="btn-cancel" on:click={closeModal}>Cancel</button>
          <button type="submit" class="btn-submit" disabled={submitting || checkingAnnouncements}>
            {#if checkingAnnouncements}
              <i class="ph-bold ph-spinner animate-spin"></i> Checking announcements...
            {:else if submitting}
              <i class="ph-bold ph-spinner animate-spin"></i> Submitting...
            {:else}
              <i class="ph-bold ph-paper-plane-right"></i> Submit Ticket
            {/if}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 20px;
  }

  .modal-card {
    background: #ffffff;
    border-radius: 16px;
    width: 100%;
    max-width: 580px;
    box-shadow: var(--shadow-lg);
    border: 1px solid var(--border-color);
    overflow: hidden;
  }

  .modal-header {
    padding: 24px;
    background: #f8fafc;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .title-group {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .modal-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: var(--primary-light);
    color: var(--primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
  }

  .title-group h2 {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .title-group p {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .close-btn {
    background: transparent;
    border: none;
    font-size: 1.2rem;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
  }

  .close-btn:hover {
    color: var(--text-main);
    background: #e2e8f0;
  }

  .error-banner {
    margin: 16px 24px 0;
    padding: 12px;
    background: var(--danger-light);
    color: var(--danger);
    border-radius: 8px;
    font-size: 0.82rem;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .modal-body {
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .routing-note {
    color: #047857;
    font-size: 0.7rem;
    line-height: 1.35;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  label {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-main);
  }

  input, select, textarea {
    padding: 10px 14px;
    border-radius: 10px;
    border: 1px solid var(--border-color);
    font-size: 0.85rem;
    color: var(--text-main);
    background: #ffffff;
    transition: all 0.15s;
  }

  input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
  }

  .announcement-notice {
    display: flex;
    gap: 11px;
    padding: 14px;
    border: 1px solid #fbbf24;
    border-radius: 11px;
    background: #fffbeb;
    color: #78350f;
  }

  .announcement-notice > i { margin-top: 2px; color: #d97706; font-size: 1.15rem; }
  .announcement-notice strong { font-size: 0.86rem; }
  .announcement-notice p { margin: 4px 0; color: #92400e; font-size: 0.84rem; font-weight: 700; }
  .announcement-notice span { display: block; color: #78350f; font-size: 0.77rem; line-height: 1.4; }
  .notice-actions { display: flex; gap: 8px; margin-top: 10px; }
  .notice-actions button { border-radius: 7px; padding: 6px 9px; font-size: 0.74rem; font-weight: 700; cursor: pointer; }
  .notice-link { border: 1px solid #f59e0b; background: white; color: #92400e; }
  .notice-submit { border: 0; background: #d97706; color: white; }

  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 10px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }

  .btn-cancel {
    padding: 10px 18px;
    border-radius: 10px;
    border: 1px solid var(--border-color);
    background: #ffffff;
    color: var(--text-muted);
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-cancel:hover {
    background: #f1f5f9;
  }

  .btn-submit {
    padding: 10px 20px;
    border-radius: 10px;
    border: none;
    background: var(--primary);
    color: #ffffff;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-submit:hover {
    background: var(--primary-hover);
  }
</style>
