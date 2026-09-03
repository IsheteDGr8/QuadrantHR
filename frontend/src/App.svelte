<script>
  import { onMount } from 'svelte';
  import Sidebar from './components/Sidebar.svelte';
  import Header from './components/Header.svelte';
  import CreateTicketModal from './components/CreateTicketModal.svelte';

  import DashboardView from './views/DashboardView.svelte';
  import InboxView from './views/InboxView.svelte';
  import KnowledgeBaseView from './views/KnowledgeBaseView.svelte';
  import AnalyticsView from './views/AnalyticsView.svelte';
  import SettingsView from './views/SettingsView.svelte';
  import CreateTicketView from './views/CreateTicketView.svelte';
  import LoginView from './views/LoginView.svelte';
  import AnnouncementsView from './views/AnnouncementsView.svelte';
  import NotificationsView from './views/NotificationsView.svelte';
  import ProfileView from './views/ProfileView.svelte';
  import OnboardingView from './views/OnboardingView.svelte';
  import TicketDetailView from './views/TicketDetailView.svelte';
  import GenieAIView from './views/GenieAIView.svelte';
  import GeneralAnalyticsView from './views/GeneralAnalyticsView.svelte';

  import { activeTab, loadTickets } from './lib/stores/tickets.js';
  import { userStore, authLoading, initAuthCheck, isTicketer } from './lib/stores/auth.js';
  import GenieAgentWidget from './components/GenieAgentWidget.svelte';

  onMount(async () => {
    console.log("🚀 [App Init] TicketGenie Svelte Application Mounting...");
    await initAuthCheck();
    if ($userStore) {
      loadTickets();
    }
  });

  $: if ($userStore) {
    console.log("👤 [App User] Active User Session:", { name: $userStore.name, role: $userStore.role, email: $userStore.email });
    loadTickets();
  } else if (!$authLoading) {
    console.log("🔒 [App User] No Active Session. Rendering Login Portal...");
  }
  $: if ($userStore && $activeTab === 'knowledge' && !isTicketer($userStore)) {
    $activeTab = 'dashboard';
  }
</script>

{#if $authLoading}
  <div class="initial-loader">
    <div class="spinner-ring"></div>
    <div class="loader-title">TicketGenie</div>
    <div class="loader-subtitle">Authenticating with Microsoft Entra ID...</div>
  </div>
{:else if !$userStore}
  <LoginView />
{:else}
  <div class="app-layout">
    <Sidebar />
    
    <div class="main-wrapper">
      <Header />
      
      <main class="content-body">
        {#if $activeTab === 'dashboard' || $activeTab === 'my-tickets'}
          <DashboardView />
        {:else if $activeTab === 'create-ticket'}
          <CreateTicketView />
        {:else if $activeTab === 'announcements'}
          <AnnouncementsView />
        {:else if $activeTab === 'notifications'}
          <NotificationsView />
        {:else if $activeTab === 'genie-ai'}
          <GenieAIView />
        {:else if $activeTab === 'profile'}
          <ProfileView />
        {:else if $activeTab === 'onboarding'}
          <OnboardingView />
        {:else if $activeTab === 'ticket-detail' || $activeTab === 'ticket-thread'}
          <TicketDetailView />
        {:else if $activeTab === 'inbox' || $activeTab === 'queue-it' || $activeTab === 'queue-hr' || $activeTab === 'queue-finance'}
          <InboxView />
        {:else if $activeTab === 'knowledge' || $activeTab === 'add-policies'}
          <KnowledgeBaseView />
        {:else if $activeTab === 'dept-analytics'}
          <AnalyticsView />
        {:else if $activeTab === 'analytics' || $activeTab === 'admin-analytics'}
          <GeneralAnalyticsView />
        {:else if $activeTab === 'settings' || $activeTab === 'rbac'}
          <SettingsView />
        {/if}
      </main>
    </div>

    <CreateTicketModal />
    {#if $activeTab !== 'genie-ai'}
      <GenieAgentWidget />
    {/if}
  </div>
{/if}

<style>
  .app-layout {
    display: flex;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    background: var(--bg-app);
  }

  .main-wrapper {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .content-body {
    flex: 1;
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    position: relative;
    display: flex;
    flex-direction: column;
  }
</style>
