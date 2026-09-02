<script>
  import { onMount } from 'svelte';
  import {
    conversations,
    selectedConversationId,
    conversationMessages,
    loadingConversations,
    loadingMessages,
    sendingMessage,
    searchQuery,
    loadConversations,
    startNewChat,
    openConversation,
    sendMessage,
    applyGenieResponseActions
  } from '../lib/stores/genieChat.js';
  import { apiExportGenieConversationPDF } from '../lib/api.js';

  let composerText = '';
  let loadError = '';
  let exportingPdf = false;

  onMount(() => {
    // Only refresh the history rail - never force a fresh New Chat here.
    // The active conversation is shared with the floating Genie popup
    // (lib/stores/genieChat.js): if the user was already chatting there,
    // opening this page must show that same conversation, not wipe it.
    // A genuinely first-ever visit already sees an empty conversation,
    // since the shared store starts empty for a freshly loaded app.
    loadConversations();
  });

  $: filteredConversations = $searchQuery.trim()
    ? $conversations.filter((c) =>
        (c.title || '').toLowerCase().includes($searchQuery.trim().toLowerCase())
      )
    : $conversations;

  function formatRelativeTime(isoString) {
    if (!isoString) return '';
    const then = new Date(isoString);
    if (Number.isNaN(then.getTime())) return '';
    const diffMs = Date.now() - then.getTime();
    const diffMin = Math.round(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.round(diffHr / 24);
    if (diffDay < 7) return `${diffDay}d ago`;
    return then.toLocaleDateString();
  }

  async function handleNewChat() {
    startNewChat();
    loadError = '';
  }

  async function handleOpenConversation(id) {
    if (id === $selectedConversationId) return;
    loadError = '';
    try {
      await openConversation(id);
    } catch (err) {
      loadError = 'Could not open that conversation. It may no longer be available.';
    }
  }

  async function handleSend() {
    const text = composerText.trim();
    if (!text || $sendingMessage) return;
    composerText = '';
    loadError = '';

    try {
      const res = await sendMessage(text);
      if (res) applyGenieResponseActions(res);
    } catch (err) {
      // conversationMessages already carries an error bubble; keep the
      // composer text cleared but don't otherwise disrupt the view.
    }
  }

  function handleComposerKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleExportPdf() {
    if (!$selectedConversationId || exportingPdf) return;
    exportingPdf = true;
    loadError = '';
    try {
      await apiExportGenieConversationPDF($selectedConversationId);
    } catch (err) {
      loadError = err.message || 'Could not export this conversation.';
    } finally {
      exportingPdf = false;
    }
  }
</script>

<div class="genie-ai-view animate-fade">
  <aside class="genie-history-panel">
    <button class="new-chat-btn" on:click={handleNewChat}>
      <i class="ph-bold ph-plus"></i>
      <span>New Chat</span>
    </button>

    <div class="search-box">
      <i class="ph-bold ph-magnifying-glass"></i>
      <input type="text" placeholder="Search chats..." bind:value={$searchQuery} />
    </div>

    <div class="conversation-list">
      {#if $loadingConversations}
        <div class="panel-state">
          <i class="ph-bold ph-spinner animate-spin"></i>
          <span>Loading chats…</span>
        </div>
      {:else if $conversations.length === 0}
        <div class="panel-state">
          <i class="ph-duotone ph-chats-circle"></i>
          <span>No previous chats yet</span>
        </div>
      {:else if filteredConversations.length === 0}
        <div class="panel-state">
          <i class="ph-bold ph-magnifying-glass"></i>
          <span>No chats match "{$searchQuery}"</span>
        </div>
      {:else}
        {#each filteredConversations as conv (conv.id)}
          <button
            class="conversation-item"
            class:active={conv.id === $selectedConversationId}
            on:click={() => handleOpenConversation(conv.id)}
            title={conv.title}
          >
            <span class="conversation-title">{conv.title}</span>
            <span class="conversation-time">{formatRelativeTime(conv.updated_at)}</span>
          </button>
        {/each}
      {/if}
    </div>
  </aside>

  <section class="genie-conversation-panel">
    <div class="conversation-toolbar">
      <button
        class="export-pdf-btn"
        on:click={handleExportPdf}
        disabled={!$selectedConversationId || exportingPdf}
        title="Download this conversation as PDF"
      >
        <i class="ph-bold {exportingPdf ? 'ph-spinner animate-spin' : 'ph-file-pdf'}"></i>
        <span>{exportingPdf ? 'Generating…' : 'Download PDF'}</span>
      </button>
    </div>
    {#if loadError}
      <div class="inline-error">{loadError}</div>
    {/if}

    {#if $loadingMessages}
      <div class="center-state">
        <i class="ph-bold ph-spinner animate-spin"></i>
        <span>Loading conversation…</span>
      </div>
    {:else if $conversationMessages.length === 0}
      <div class="empty-state">
        <div class="empty-state-icon"><i class="ph-fill ph-sparkle"></i></div>
        <h2>How can Genie help you today?</h2>
        <p>Ask about IT/HR policies, ticket status, or start a new request - Genie can draft it for you.</p>
      </div>
    {:else}
      <div class="messages-list">
        {#each $conversationMessages as msg}
          <div class="message-row" class:message-row-user={msg.role === 'user'}>
            {#if msg.role !== 'user'}
              <div class="message-avatar"><i class="ph-fill ph-ticket"></i></div>
            {/if}
            <div class="message-bubble" class:message-bubble-error={msg.isError}>{msg.content}</div>
          </div>
        {/each}

        {#if $sendingMessage}
          <div class="message-row">
            <div class="message-avatar"><i class="ph-fill ph-ticket"></i></div>
            <div class="message-bubble typing"><i class="ph-bold ph-spinner animate-spin"></i> Genie is thinking...</div>
          </div>
        {/if}
      </div>
    {/if}

    <div class="composer">
      <textarea
        rows="1"
        placeholder="Message Genie AI..."
        bind:value={composerText}
        on:keydown={handleComposerKeydown}
        disabled={$sendingMessage}
      ></textarea>
      <button class="send-btn" on:click={handleSend} disabled={$sendingMessage || !composerText.trim()}>
        <i class="ph-bold ph-paper-plane-right"></i>
      </button>
    </div>
    <div class="ai-disclaimer" role="note">
      Genie uses artificial intelligence and may provide inaccurate or incomplete information. Verify important details before acting.
    </div>
  </section>
</div>

<style>
  .genie-ai-view {
    height: 100%;
    display: flex;
    min-height: 0;
  }

  /* -------- Left history rail -------- */
  .genie-history-panel {
    width: 280px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 20px 14px;
    border-right: 1px solid var(--border-color);
    background: var(--bg-app, #f8fafc);
    overflow-y: auto;
  }

  .new-chat-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 42px;
    border: 1px solid var(--primary);
    background: var(--primary);
    color: white;
    border-radius: 10px;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .new-chat-btn:hover {
    background: var(--primary-hover, #4338ca);
  }

  .search-box {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 38px;
    padding: 0 12px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: white;
    flex-shrink: 0;
    color: var(--text-muted);
  }

  .search-box input {
    flex: 1;
    border: none;
    outline: none;
    font-size: 0.82rem;
    color: var(--text-main);
    background: transparent;
  }

  .conversation-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .conversation-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 10px 12px;
    border: none;
    background: transparent;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s;
    width: 100%;
  }

  .conversation-item:hover {
    background: rgba(79, 70, 229, 0.08);
  }

  .conversation-item.active {
    background: rgba(79, 70, 229, 0.12);
  }

  .conversation-title {
    font-size: 0.83rem;
    font-weight: 600;
    color: var(--text-main);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .conversation-time {
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  .panel-state,
  .center-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 32px 12px;
    color: var(--text-muted);
    font-size: 0.8rem;
    text-align: center;
  }

  .panel-state i,
  .center-state i {
    font-size: 1.4rem;
  }

  /* -------- Right conversation panel -------- */
  .genie-conversation-panel {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .conversation-toolbar {
    min-height: 58px;
    padding: 10px 24px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    border-bottom: 1px solid var(--border-color);
    background: #fff;
    box-sizing: border-box;
    flex-shrink: 0;
  }

  .export-pdf-btn {
    border: 1px solid #fca5a5;
    border-radius: 9px;
    padding: 9px 13px;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: #fef2f2;
    color: #b91c1c;
    font: inherit;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
  }

  .export-pdf-btn:hover:not(:disabled) {
    background: #dc2626;
    border-color: #dc2626;
    color: #fff;
  }

  .export-pdf-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .inline-error {
    margin: 12px 24px 0;
    padding: 10px 14px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #b91c1c;
    border-radius: 8px;
    font-size: 0.82rem;
    flex-shrink: 0;
  }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 24px;
    gap: 10px;
  }

  .empty-state-icon {
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background: #2b1b38;
    color: #facc15;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    margin-bottom: 6px;
  }

  .empty-state h2 {
    margin: 0;
    font-size: 1.3rem;
    color: var(--text-main);
  }

  .empty-state p {
    margin: 0;
    max-width: 420px;
    color: var(--text-muted);
    font-size: 0.88rem;
  }

  .messages-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .message-row {
    display: flex;
    gap: 10px;
  }

  .message-row-user {
    justify-content: flex-end;
  }

  .message-avatar {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: #e0e7ff;
    color: #4f46e5;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 0.95rem;
  }

  .message-bubble {
    max-width: 560px;
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 4px 14px 14px 14px;
    padding: 11px 16px;
    color: var(--text-main);
    font-size: 0.88rem;
    line-height: 1.5;
    box-shadow: var(--shadow-sm);
    white-space: pre-line;
  }

  .message-bubble.typing {
    color: var(--text-muted);
    font-style: italic;
  }

  .message-bubble-error {
    border-color: #fecaca;
    background: #fef2f2;
    color: #b91c1c;
  }

  .message-row-user .message-bubble {
    background: #4f46e5;
    color: white;
    border-color: #4f46e5;
    border-radius: 14px 4px 14px 14px;
  }

  .composer {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    padding: 16px 24px 10px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
    background: white;
  }

  .ai-disclaimer {
    padding: 0 24px 14px;
    background: #fff;
    color: var(--text-muted);
    text-align: center;
    font-size: 0.7rem;
    line-height: 1.4;
    flex-shrink: 0;
  }

  .composer textarea {
    flex: 1;
    resize: none;
    max-height: 140px;
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 0.88rem;
    font-family: inherit;
    outline: none;
    color: var(--text-main);
  }

  .composer textarea:focus {
    border-color: var(--primary);
  }

  .send-btn {
    width: 42px;
    height: 42px;
    flex-shrink: 0;
    border: none;
    border-radius: 10px;
    background: var(--primary);
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }

  .send-btn:hover:not(:disabled) {
    background: var(--primary-hover, #4338ca);
  }

  .send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* -------- Responsive: narrow the history rail on smaller desktop/tablet widths -------- */
  @media (max-width: 1024px) {
    .genie-history-panel {
      width: 220px;
    }

    .conversation-time {
      display: none;
    }
  }

  @media (max-width: 820px) {
    .genie-history-panel {
      width: 64px;
      padding: 16px 8px;
    }

    .new-chat-btn span,
    .search-box input,
    .conversation-title,
    .conversation-time {
      display: none;
    }

    .new-chat-btn {
      padding: 0;
      width: 42px;
      align-self: center;
    }

    .search-box {
      justify-content: center;
      padding: 0;
    }

    .conversation-item {
      align-items: center;
    }
  }
</style>
