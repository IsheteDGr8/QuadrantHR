<script>
  import { activeTab } from '../lib/stores/tickets.js';
  import { userStore } from '../lib/stores/auth.js';

  export let requiredRoleName = 'Admin / Ticketer';

  function returnToDashboard() {
    $activeTab = 'dashboard';
  }
</script>

<div class="access-denied-container animate-fade">
  <div class="denied-card">
    <div class="icon-box">
      <i class="ph-duotone ph-shield-warning"></i>
    </div>
    <h2>Access Restricted</h2>
    <p>
      Your account <strong>{$userStore?.email || 'User'}</strong> with role 
      <span class="role-badge">{$userStore?.role || 'Employee'}</span> 
      does not have permission to access this portal page.
    </p>
    <p class="sub-text">
      This page requires <strong>{requiredRoleName}</strong> permissions.
    </p>

    <button class="btn-return" on:click={returnToDashboard}>
      <i class="ph-bold ph-arrow-left"></i> Return to Operations Dashboard
    </button>
  </div>
</div>

<style>
  .access-denied-container {
    padding: 60px 28px;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
  }

  .denied-card {
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 40px;
    max-width: 480px;
    text-align: center;
    box-shadow: var(--shadow-md);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }

  .icon-box {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: var(--danger-light);
    color: var(--danger);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.2rem;
  }

  .denied-card h2 {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .denied-card p {
    font-size: 0.88rem;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .role-badge {
    background: var(--primary-light);
    color: var(--primary);
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.8rem;
  }

  .sub-text {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .btn-return {
    margin-top: 10px;
    background: var(--primary);
    color: #ffffff;
    border: none;
    padding: 10px 20px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s;
  }

  .btn-return:hover {
    background: var(--primary-hover);
  }
</style>
