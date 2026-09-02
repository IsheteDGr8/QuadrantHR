<script>
  import { onMount, onDestroy } from 'svelte';
  import { activeTab } from '../lib/stores/tickets.js';
  import { userStore } from '../lib/stores/auth.js';
  import { apiFetchLatestAnnouncementWithSeverity } from '../lib/api.js';

  let latestAnnouncement = null;
  let severity = { level: 'info', label: 'ANNOUNCEMENT', icon: 'ph-megaphone', color_class: 'severity-info' };
  let abortController = null;

  onMount(async () => {
    abortController = new AbortController();
    try {
      const data = await apiFetchLatestAnnouncementWithSeverity(abortController.signal);
      if (data && data.announcement) {
        latestAnnouncement = data.announcement;
        if (data.severity) {
          severity = data.severity;
        }
      }
    } catch (err) {
      if (err?.name !== 'AbortError') {
        console.warn("Failed to load header announcement with AI severity from backend:", err);
      }
    }
  });

  onDestroy(() => {
    if (abortController) {
      abortController.abort();
    }
  });
</script>

<header class="header">
  <div class="header-left">
    {#if latestAnnouncement}
      <!-- svelte-ignore a11y-click-events-have-key-events a11y-interactive-supports-focus -->
      <div 
        class="announcement-banner {severity.color_class || severity.colorClass || 'severity-info'} animate-fade"
        on:click={() => $activeTab = 'announcements'}
        role="button"
        tabindex="0"
        title="Click to view all company announcements"
      >
        <span class="severity-pill">
          <i class="ph-bold {severity.icon || 'ph-megaphone'}"></i> {severity.label || 'ANNOUNCEMENT'}
        </span>
        <span class="banner-title">{latestAnnouncement.title}</span>
        {#if latestAnnouncement.content}
          <span class="banner-snippet">— {latestAnnouncement.content}</span>
        {/if}
        <i class="ph-bold ph-arrow-right banner-arrow"></i>
      </div>
    {:else}
      <div class="header-branding">
        <span class="portal-tag">TicketGenie Service Portal</span>
      </div>
    {/if}
  </div>

  <div class="header-actions">
    <!-- Azure AD Authenticated Badge -->
    <div class="azure-badge">
      <i class="ph-bold ph-shield-check icon"></i>
      <span>Azure AD: <code>Bearer Token</code></span>
    </div>

    <!-- Authenticated User Profile Badge -->
    <div class="user-profile-badge">
      <i class="ph-duotone ph-user-circle"></i>
      <span>{$userStore?.name || 'Employee User'}</span>
    </div>
  </div>
</header>

<style>
  .header {
    height: 70px;
    background: var(--bg-card);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 28px;
    gap: 20px;
    z-index: 10;
  }

  .header-left {
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 0;
  }

  .header-branding {
    display: flex;
    align-items: center;
  }

  .portal-tag {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--text-main);
    letter-spacing: -0.01em;
  }

  .announcement-banner {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 7px 14px;
    border-radius: 10px;
    cursor: pointer;
    font-size: 0.82rem;
    max-width: 680px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: all 0.2s ease;
    border: 1px solid transparent;
  }

  .announcement-banner:hover {
    transform: translateY(-1px);
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.06);
  }

  .severity-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.7rem;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 6px;
    letter-spacing: 0.03em;
    flex-shrink: 0;
  }

  .banner-title {
    font-weight: 700;
    flex-shrink: 0;
  }

  .banner-snippet {
    color: inherit;
    opacity: 0.85;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .banner-arrow {
    font-size: 0.8rem;
    opacity: 0.7;
    margin-left: 2px;
    flex-shrink: 0;
  }

  /* Severity Color Schemes */
  .severity-critical {
    background: #fef2f2;
    border-color: #fecaca;
    color: #991b1b;
  }
  .severity-critical .severity-pill {
    background: #dc2626;
    color: #ffffff;
  }

  .severity-warning {
    background: #fffbeb;
    border-color: #fde68a;
    color: #92400e;
  }
  .severity-warning .severity-pill {
    background: #d97706;
    color: #ffffff;
  }

  .severity-info {
    background: #eff6ff;
    border-color: #bfdbfe;
    color: #1e40af;
  }
  .severity-info .severity-pill {
    background: #3b82f6;
    color: #ffffff;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;
  }

  .azure-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f1f5f9;
    padding: 6px 12px;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    font-size: 0.78rem;
    color: #475569;
  }

  .azure-badge .icon {
    color: var(--success);
  }

  .azure-badge code {
    background: #e0e7ff;
    color: #3730a3;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-weight: 600;
  }

  .user-profile-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f8fafc;
    border: 1px solid var(--border-color);
    padding: 8px 14px;
    border-radius: 10px;
    font-size: 0.83rem;
    font-weight: 600;
    color: var(--text-main);
  }

  .user-profile-badge i {
    font-size: 1.2rem;
    color: var(--primary);
  }
</style>
