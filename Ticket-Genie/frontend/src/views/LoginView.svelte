<script>
  import { userStore, azureAuthStatus, loginWithAzureAD } from '../lib/stores/auth.js';
  import { onMount } from 'svelte';

  onMount(() => {
    console.log("🔐 [Login Portal] Mounted LoginView screen. Auto-initiating Azure AD authentication...");
    handleAzureSignIn();
  });

  function handleAzureSignIn() {
    console.log("🚀 [Login Portal] Sign In with Azure AD button clicked.");
    loginWithAzureAD();
  }
</script>

<div class="login-page">
  <div class="login-wrapper animate-fade">
    <div class="login-header">
      <h1><span class="bot-icon"><i class="ph-fill ph-ticket"></i></span> TicketGenie</h1>
      <p>Enterprise Microsoft Entra ID Authentication</p>
    </div>
    
    <div class="portal-container">
      <!-- Azure AD Status Badge -->
      <div class="azure-status">
        <i class="ph-bold ph-shield-check" style="color: #10b981; font-size: 1rem;"></i>
        <span>Azure AD: <code>{$azureAuthStatus}</code></span>
      </div>

      <!-- Primary Azure AD OAuth Sign In Button -->
      <button class="azure-signin-btn" on:click={handleAzureSignIn}>
        <i class="ph-bold ph-windows-logo"></i>
        <span>Sign In with Azure AD (SSO)</span>
      </button>
    </div>
  </div>
</div>

<style>
  .login-page {
    width: 100vw;
    height: 100vh;
    background-color: #f4f5f8;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
  }

  .login-wrapper {
    width: 100%;
    max-width: 520px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.06);
    border: 1px solid #e5e7eb;
    overflow: hidden;
  }

  .login-header {
    background-color: #2b1b38;
    padding: 36px 24px;
    text-align: center;
    color: white;
  }

  .login-header h1 {
    font-size: 1.6rem;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-weight: 700;
  }

  .login-header p {
    color: #a5b4fc;
    font-size: 0.9rem;
  }

  .bot-icon {
    background: rgba(255,255,255,0.1);
    color: #facc15;
    padding: 6px 10px;
    border-radius: 10px;
    font-size: 1.3rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .portal-container {
    padding: 32px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .azure-signin-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    width: 100%;
    padding: 14px 20px;
    background: #0078d4;
    color: #ffffff;
    border: none;
    border-radius: 12px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(0, 120, 212, 0.25);
  }

  .azure-signin-btn:hover {
    background: #005a9e;
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(0, 120, 212, 0.35);
  }

  .azure-status {
    font-size: 0.78rem;
    color: #334155;
    background: #f8fafc;
    padding: 10px 14px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    text-align: center;
    display: flex;
    align-items: center;
    gap: 8px;
    justify-content: center;
    margin-bottom: 4px;
  }

  .azure-status code {
    font-family: monospace;
    font-weight: 600;
    color: #2563eb;
    background: #eff6ff;
    padding: 2px 6px;
    border-radius: 4px;
  }
</style>
