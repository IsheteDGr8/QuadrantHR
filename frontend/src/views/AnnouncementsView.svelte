<script>
  import { onMount } from 'svelte';
  import { apiCreateAnnouncement, apiDeleteAnnouncement, apiFetchAnnouncements } from '../lib/api.js';
  import { userStore } from '../lib/stores/auth.js';

  let announcements = [];
  let loading = true;
  let isCreateOpen = false;
  let isSubmitting = false;
  let formError = '';
  let title = '';
  let category = 'General Alert';
  let content = '';
  let deletingId = null;

  $: normalizedRole = ($userStore?.role || '').trim().toLowerCase().replace('_', ' ');
  $: canCreate = ['admin', 'ticketer', 'support', 'agent', 'super'].some((role) => normalizedRole.includes(role));

  onMount(loadAnnouncements);

  async function loadAnnouncements() {
    loading = true;
    announcements = await apiFetchAnnouncements();
    loading = false;
  }

  function closeCreateModal() {
    if (isSubmitting) return;
    isCreateOpen = false;
    formError = '';
  }

  async function submitAnnouncement() {
    if (!title.trim() || !content.trim()) {
      formError = 'Title and announcement details are required.';
      return;
    }
    isSubmitting = true;
    formError = '';
    try {
      const created = await apiCreateAnnouncement({ title: title.trim(), category, content: content.trim() });
      announcements = [created, ...announcements.filter((item) => item.id !== created.id)];
      title = '';
      category = 'General Alert';
      content = '';
      isCreateOpen = false;
    } catch (error) {
      formError = error.message || 'Unable to create the announcement.';
    } finally {
      isSubmitting = false;
    }
  }

  async function removeAnnouncement(item) {
    if (!confirm(`Delete “${item.title}”? This cannot be undone.`)) return;
    deletingId = item.id;
    formError = '';
    try {
      await apiDeleteAnnouncement(item.id);
      announcements = announcements.filter((announcement) => announcement.id !== item.id);
    } catch (error) {
      formError = error.message || 'Unable to delete the announcement.';
    } finally {
      deletingId = null;
    }
  }

  function formatDate(item) {
    const rawDate = item.createdAt || item.date;
    if (!rawDate) return '';
    const parsed = new Date(rawDate);
    return Number.isNaN(parsed.getTime()) ? rawDate : parsed.toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  }
</script>

<div class="announcements-view animate-fade">
  <div class="view-header">
    <div>
      <h1 class="view-title"><i class="ph-bold ph-megaphone"></i> Company Announcements</h1>
      <p class="view-subtitle">Official corporate news, operational notices, and IT system maintenance windows</p>
    </div>
    {#if canCreate}
      <button class="create-button" on:click={() => { formError = ''; isCreateOpen = true; }}>
        <i class="ph-bold ph-plus"></i> Create Announcement
      </button>
    {/if}
  </div>

  {#if formError && !isCreateOpen}<div class="form-error" role="alert">{formError}</div>{/if}

  {#if loading}
    <div class="loading-state"><i class="ph-bold ph-spinner animate-spin"></i> Loading announcements...</div>
  {:else if announcements.length === 0}
    <div class="empty-state">
      <i class="ph-duotone ph-megaphone"></i>
      <h2>No announcements yet</h2>
      <p>Company-wide announcements will appear here.</p>
    </div>
  {:else}
    <div class="announcements-list">
      {#each announcements as item (item.id)}
        <div class="announcement-card">
          <div class="card-header">
            <div>
              <span class="category-chip">{item.category}</span>
              <h2>{item.title}</h2>
            </div>
            <div class="card-actions">
              <span class="date-chip"><i class="ph-bold ph-calendar"></i> {formatDate(item)}</span>
              {#if canCreate}
                <button class="delete-button" on:click={() => removeAnnouncement(item)} disabled={deletingId === item.id} aria-label={`Delete ${item.title}`}>
                  <i class="ph-bold {deletingId === item.id ? 'ph-spinner animate-spin' : 'ph-trash'}"></i>
                  {deletingId === item.id ? 'Deleting...' : 'Delete'}
                </button>
              {/if}
            </div>
          </div>
          <p class="card-content">{item.content}</p>
          {#if item.author}<p class="card-author"><i class="ph-bold ph-user-circle"></i> Posted by {item.author}</p>{/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if isCreateOpen && canCreate}
  <div class="modal-backdrop" role="presentation" on:click={(event) => event.target === event.currentTarget && closeCreateModal()}>
    <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="announcement-modal-title">
      <div class="modal-header">
        <div>
          <h2 id="announcement-modal-title"><i class="ph-duotone ph-megaphone"></i> Create Announcement</h2>
          <p>This announcement will be visible to every TicketGenie user.</p>
        </div>
        <button class="close-button" aria-label="Close" on:click={closeCreateModal} disabled={isSubmitting}><i class="ph-bold ph-x"></i></button>
      </div>
      <form on:submit|preventDefault={submitAnnouncement}>
        <div class="modal-body">
          {#if formError}<div class="form-error" role="alert">{formError}</div>{/if}
          <div class="form-group">
            <label for="announcement-title">Title</label>
            <input id="announcement-title" maxlength="200" placeholder="e.g. Office closure this Friday" bind:value={title} disabled={isSubmitting} />
          </div>
          <div class="form-group">
            <label for="announcement-category">Category</label>
            <select id="announcement-category" bind:value={category} disabled={isSubmitting}>
              <option>General Alert</option><option>Company News</option><option>IT System Update</option>
              <option>HR &amp; Operations</option><option>Policy Update</option>
            </select>
          </div>
          <div class="form-group">
            <label for="announcement-content">Announcement details</label>
            <textarea id="announcement-content" rows="6" maxlength="10000" placeholder="Share the information all employees need to know..." bind:value={content} disabled={isSubmitting}></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="secondary-button" on:click={closeCreateModal} disabled={isSubmitting}>Cancel</button>
          <button type="submit" class="primary-button" disabled={isSubmitting}>
            {#if isSubmitting}<i class="ph-bold ph-spinner animate-spin"></i> Publishing...{:else}<i class="ph-bold ph-paper-plane-tilt"></i> Publish Announcement{/if}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  .announcements-view { padding: 28px; display: flex; flex-direction: column; gap: 24px; height: 100%; overflow-y: auto; }
  .view-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
  .view-title { font-size: 1.5rem; font-weight: 700; color: var(--text-main); }
  .view-subtitle { font-size: 0.85rem; color: var(--text-muted); }
  .create-button, .primary-button { border: 0; border-radius: 10px; background: var(--primary); color: white; padding: 11px 16px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 7px; }
  .create-button:hover, .primary-button:hover { filter: brightness(0.94); }
  .loading-state, .empty-state { padding: 40px; text-align: center; color: var(--text-muted); font-weight: 600; }
  .empty-state { background: white; border: 1px dashed var(--border-color); border-radius: var(--border-radius); max-width: 860px; }
  .empty-state i { font-size: 2rem; color: var(--primary); }
  .empty-state h2 { margin-top: 8px; color: var(--text-main); font-size: 1.05rem; }
  .empty-state p { margin-top: 4px; font-size: 0.85rem; }
  .announcements-list { display: flex; flex-direction: column; gap: 18px; max-width: 860px; }
  .announcement-card { background: white; border: 1px solid var(--border-color); border-left: 4px solid var(--primary); border-radius: var(--border-radius); padding: 24px; box-shadow: var(--shadow-sm); }
  .card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 12px; }
  .category-chip { font-size: 0.72rem; font-weight: 700; color: var(--primary); background: var(--primary-light); padding: 2px 8px; border-radius: 6px; text-transform: uppercase; }
  .card-header h2 { font-size: 1.15rem; font-weight: 700; color: var(--text-main); margin-top: 6px; }
  .date-chip { flex-shrink: 0; font-size: 0.8rem; color: var(--text-muted); font-weight: 600; }
  .card-actions { display: flex; align-items: center; gap: 12px; }
  .delete-button { border: 1px solid #fecaca; border-radius: 8px; padding: 7px 10px; color: #b91c1c; background: #fff7f7; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
  .delete-button:hover { background: #fee2e2; }
  .card-content { font-size: 0.88rem; color: var(--text-main); line-height: 1.6; white-space: pre-wrap; }
  .card-author { margin-top: 14px; color: var(--text-muted); font-size: 0.78rem; font-weight: 600; }
  .modal-backdrop { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(15, 23, 42, 0.55); backdrop-filter: blur(3px); }
  .modal-card { width: min(560px, 100%); overflow: hidden; background: white; border-radius: 16px; box-shadow: 0 24px 60px rgba(15, 23, 42, 0.24); }
  .modal-header { display: flex; justify-content: space-between; gap: 20px; padding: 22px 24px; border-bottom: 1px solid var(--border-color); }
  .modal-header h2 { color: var(--text-main); font-size: 1.2rem; }
  .modal-header p { margin-top: 4px; color: var(--text-muted); font-size: 0.8rem; }
  .close-button { width: 34px; height: 34px; border: 0; border-radius: 8px; color: var(--text-muted); background: var(--bg-app); cursor: pointer; }
  .modal-body { display: flex; flex-direction: column; gap: 16px; padding: 22px 24px; }
  .form-group { display: flex; flex-direction: column; gap: 7px; }
  .form-group label { color: var(--text-main); font-size: 0.82rem; font-weight: 700; }
  .form-group input, .form-group select, .form-group textarea { width: 100%; border: 1px solid var(--border-color); border-radius: 9px; padding: 10px 12px; color: var(--text-main); background: white; font: inherit; font-size: 0.87rem; outline: none; }
  .form-group textarea { resize: vertical; }
  .form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-light); }
  .form-error { border-radius: 8px; padding: 10px 12px; color: #b91c1c; background: #fef2f2; font-size: 0.82rem; font-weight: 600; }
  .modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 18px 24px; border-top: 1px solid var(--border-color); background: #fafafa; }
  .secondary-button { border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 15px; color: var(--text-main); background: white; font-weight: 700; cursor: pointer; }
  button:disabled { cursor: not-allowed; opacity: 0.65; }
  @media (max-width: 640px) { .view-header, .card-header { align-items: stretch; flex-direction: column; } .create-button { width: 100%; } }
</style>
