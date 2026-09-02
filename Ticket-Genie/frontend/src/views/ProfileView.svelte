<script>
  import { userStore, logout } from '../lib/stores/auth.js';

  $: user = $userStore;
</script>

<div class="profile-view animate-fade">
  <div class="view-header">
    <div>
      <h1 class="view-title"><i class="ph-bold ph-user-gear"></i> Profile & Credentials</h1>
      <p class="view-subtitle">Authenticated Azure AD / Microsoft Entra ID session details and bearer token inspect</p>
    </div>
    <button class="btn-logout" on:click={logout}>
      <i class="ph-bold ph-sign-out"></i> Sign Out Session
    </button>
  </div>

  <div class="profile-card">
    <div class="user-info-row">
      <div class="avatar-circle">
        <i class="ph-bold ph-user"></i>
      </div>
      <div>
        <h2>{user?.name || 'Authenticated User'}</h2>
        <p class="user-email">{user?.email || 'user@company.com'}</p>
        <span class="role-badge">{user?.role || 'Employee'}</span>
      </div>
    </div>

    <div class="details-grid">
      <div class="detail-item">
        <span class="label">Azure Object ID (OID)</span>
        <code class="val-code">{user?.objectId || user?.azure_object_id || user?.oid || 'usr-emp-001'}</code>
      </div>
      <div class="detail-item">
        <span class="label">Department</span>
        <span class="val">{user?.department || 'Operations'}</span>
      </div>
      <div class="detail-item">
        <span class="label">Identity Provider</span>
        <span class="val">Microsoft Entra ID (Azure AD MSAL)</span>
      </div>
      <div class="detail-item">
        <span class="label">Session Status</span>
        <span class="val-status"><span class="status-dot"></span> JWT Verified</span>
      </div>
    </div>

    <div class="token-box">
      <h3><i class="ph-bold ph-key"></i> Active Bearer Token Payload</h3>
      <textarea rows="4" readonly>{user?.idToken || 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6ImZFdHF... (Verified Zero-Trust Session)'}</textarea>
    </div>
  </div>
</div>

<style>
  .profile-view {
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

  .btn-logout {
    padding: 10px 18px;
    border-radius: 10px;
    border: 1px solid #fca5a5;
    background: #fef2f2;
    color: #dc2626;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .profile-card {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 32px;
    max-width: 760px;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .user-info-row {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .avatar-circle {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--primary-light);
    color: var(--primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
  }

  .user-info-row h2 {
    font-size: 1.3rem;
    font-weight: 700;
  }

  .user-email {
    font-size: 0.88rem;
    color: var(--text-muted);
  }

  .role-badge {
    display: inline-block;
    margin-top: 6px;
    background: #e0e7ff;
    color: #3730a3;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 700;
  }

  .details-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    background: #f8fafc;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid var(--border-color);
  }

  .detail-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .label {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .val-code {
    font-family: monospace;
    font-size: 0.82rem;
    color: var(--primary);
  }

  .val {
    font-size: 0.9rem;
    font-weight: 600;
  }

  .val-status {
    font-size: 0.85rem;
    font-weight: 600;
    color: #059669;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
  }

  .token-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .token-box h3 {
    font-size: 0.9rem;
    font-weight: 700;
  }

  textarea {
    width: 100%;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    font-family: monospace;
    font-size: 0.78rem;
    background: #f8fafc;
    color: var(--text-muted);
    resize: none;
  }
</style>
