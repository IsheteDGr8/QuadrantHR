<script>
  import { onMount } from 'svelte';
  import { apiFetchNotifications, apiMarkNotificationRead } from '../lib/api.js';

  let notifications = [];
  let loading = true;
  let errorMessage = '';
  let markingAll = false;
  $: unreadCount = notifications.filter((item) => !item.is_read).length;

  async function loadNotifications() {
    loading = true;
    errorMessage = '';
    try { notifications = await apiFetchNotifications(); }
    catch (error) { errorMessage = error.message || 'Unable to load notifications.'; }
    finally { loading = false; }
  }

  async function markRead(item) {
    if (item.is_read) return;
    try {
      await apiMarkNotificationRead(item.id);
      notifications = notifications.map((entry) => entry.id === item.id ? { ...entry, is_read: true } : entry);
    } catch (error) { errorMessage = error.message || 'Unable to update the notification.'; }
  }

  async function markAllRead() {
    const unread = notifications.filter((item) => !item.is_read);
    if (!unread.length) return;
    markingAll = true;
    errorMessage = '';
    try {
      await Promise.all(unread.map((item) => apiMarkNotificationRead(item.id)));
      notifications = notifications.map((item) => ({ ...item, is_read: true }));
    } catch (error) {
      errorMessage = error.message || 'Unable to mark all notifications as read.';
      await loadNotifications();
    } finally { markingAll = false; }
  }

  function relativeTime(value) {
    const timestamp = new Date(value).getTime();
    if (!Number.isFinite(timestamp)) return '';
    const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)} days ago`;
    return new Date(value).toLocaleDateString();
  }

  function iconFor(item) {
    const text = `${item.title} ${item.message}`.toLowerCase();
    if (text.includes('ticket') || text.includes('comment')) return 'ph-ticket';
    if (text.includes('leave') || text.includes('pto')) return 'ph-calendar-check';
    return 'ph-bell-ringing';
  }

  onMount(loadNotifications);
</script>

<div class="notifications-view animate-fade">
  <div class="view-header">
    <div>
      <h1 class="view-title"><i class="ph-bold ph-bell"></i> Notifications</h1>
      <p class="view-subtitle">{unreadCount ? `${unreadCount} unread notification${unreadCount === 1 ? '' : 's'}` : 'You are up to date'}</p>
    </div>
    <button class="btn-read-all" on:click={markAllRead} disabled={loading || markingAll || !unreadCount}>
      <i class="ph-bold ph-checks"></i> {markingAll ? 'Updating…' : 'Mark All as Read'}
    </button>
  </div>

  {#if errorMessage}
    <div class="state-message error" role="alert"><span>{errorMessage}</span><button on:click={loadNotifications}>Try again</button></div>
  {/if}

  {#if loading}
    <div class="state-message"><i class="ph ph-spinner-gap spinner"></i> Loading notifications…</div>
  {:else if notifications.length === 0}
    <div class="empty-state"><i class="ph ph-bell-slash"></i><h3>You’re all caught up</h3><p>Ticket updates and replies will appear here.</p></div>
  {:else}
    <div class="notifications-list">
      {#each notifications as item (item.id)}
        <button class="notification-item" class:unread={!item.is_read} on:click={() => markRead(item)}>
          <span class="notif-icon"><i class={`ph-fill ${iconFor(item)}`}></i></span>
          <span class="notif-body">
            <span class="notif-header"><strong>{item.title}</strong><span class="notif-time">{relativeTime(item.createdAt)}</span></span>
            <span class="notif-message">{item.message}</span>
          </span>
          {#if !item.is_read}<span class="unread-dot" aria-label="Unread"></span>{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .notifications-view { padding: 28px; display: flex; flex-direction: column; gap: 24px; height: 100%; overflow-y: auto; }
  .view-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
  .view-title { font-size: 1.5rem; font-weight: 700; color: var(--text-main); }
  .view-subtitle { margin-top: 4px; font-size: .85rem; color: var(--text-muted); }
  .btn-read-all { padding: 10px 18px; border-radius: 10px; border: 1px solid var(--border-color); background: white; color: var(--text-main); font-weight: 600; font-size: .85rem; cursor: pointer; display: flex; align-items: center; gap: 8px; }
  .btn-read-all:disabled { cursor: not-allowed; opacity: .5; }
  .notifications-list { display: flex; flex-direction: column; gap: 12px; max-width: 850px; }
  .notification-item { width: 100%; text-align: left; font: inherit; color: inherit; background: white; border: 1px solid var(--border-color); border-radius: var(--border-radius); padding: 18px; display: flex; align-items: flex-start; gap: 16px; box-shadow: var(--shadow-sm); cursor: pointer; }
  .notification-item.unread { border-left: 4px solid var(--primary); background: #f8fafc; }
  .notif-icon { width: 40px; height: 40px; border-radius: 10px; background: var(--primary-light); color: var(--primary); display: flex; align-items: center; justify-content: center; font-size: 1.2rem; flex-shrink: 0; }
  .notif-body { flex: 1; min-width: 0; }
  .notif-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 4px; }
  .notif-header strong { font-size: .95rem; }
  .notif-time { white-space: nowrap; font-size: .78rem; color: var(--text-muted); }
  .notif-message { display: block; font-size: .85rem; color: var(--text-main); }
  .unread-dot { width: 8px; height: 8px; margin-top: 7px; border-radius: 50%; background: var(--primary); flex-shrink: 0; }
  .state-message, .empty-state { max-width: 850px; padding: 28px; border: 1px solid var(--border-color); border-radius: var(--border-radius); background: white; color: var(--text-muted); text-align: center; }
  .state-message.error { display: flex; justify-content: space-between; align-items: center; color: #b91c1c; }
  .state-message button { border: 0; background: transparent; color: var(--primary); font-weight: 700; cursor: pointer; }
  .empty-state i { font-size: 2.5rem; color: var(--text-muted); }
  .empty-state h3 { margin-top: 10px; color: var(--text-main); }
  .empty-state p { margin-top: 4px; font-size: .88rem; }
  .spinner { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (max-width: 640px) { .notifications-view { padding: 20px; } .view-header { align-items: flex-start; flex-direction: column; } .notif-header { align-items: flex-start; flex-direction: column; gap: 2px; } }
</style>
