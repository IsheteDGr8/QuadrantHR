<script>
  // Compact popup drawer over the SAME conversation the full Genie AI page
  // (views/GenieAIView.svelte) shows - both read/write the shared
  // lib/stores/genieChat.js store (conversationMessages, sendingMessage,
  // sendMessage, applyGenieResponseActions), so a message sent here is
  // immediately visible on the page and vice versa. This popup never keeps
  // its own history array, never calls the chatbot API directly, and never
  // re-implements navigation/ticket-draft handling - see genieChat.js.
  import { afterUpdate } from 'svelte';
  import { conversationMessages, sendingMessage, suggestions, sendMessage, applyGenieResponseActions } from '../lib/stores/genieChat.js';

  let isOpen = false;
  let userMessage = '';
  let messagesContainer;

  afterUpdate(() => {
    if (isOpen && messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });

  function toggleChat() {
    isOpen = !isOpen;
  }

  async function handleSend(textToSend = null) {
    const text = textToSend || userMessage.trim();
    if (!text || $sendingMessage) return;
    userMessage = '';

    try {
      const res = await sendMessage(text);
      if (res) applyGenieResponseActions(res);
    } catch (err) {
      // conversationMessages already carries an error bubble via the
      // shared store - nothing else to do here.
    }
  }
</script>

<!-- Floating AI Assistant Launcher Button -->
<div class="genie-container">
  <button class="genie-button" on:click={toggleChat} title="Open AI TicketGenie Assistant">
    <i class="ph-fill ph-sparkle"></i>
    <span>Genie AI</span>
  </button>
</div>

<!-- Floating AI Assistant Chat Drawer -->
{#if isOpen}
  <div class="genie-chat open animate-fade">
    <div class="genie-chat-header">
      <div class="genie-header-info">
        <div class="genie-avatar">
          <i class="ph-fill ph-ticket"></i>
        </div>
        <div>
          <h4>TicketGenie AI Assistant</h4>
          <span class="status-indicator"><span class="genie-status-dot"></span> Active Engine</span>
        </div>
      </div>
      <button class="genie-close" on:click={toggleChat}><i class="ph-bold ph-x"></i></button>
    </div>

    <!-- Messages Container -->
    <div class="genie-messages" bind:this={messagesContainer}>
      {#if $conversationMessages.length === 0}
        <div class="genie-message">
          <div class="genie-message-avatar"><i class="ph-fill ph-ticket"></i></div>
          <div class="genie-bubble">Hi there! I am Genie, your AI support agent. How can I help you today?</div>
        </div>
      {:else}
        {#each $conversationMessages as msg}
          <div class="genie-message" class:genie-message-user={msg.role === 'user'}>
            {#if msg.role !== 'user'}
              <div class="genie-message-avatar"><i class="ph-fill ph-ticket"></i></div>
            {/if}
            <div class="genie-bubble" class:genie-bubble-error={msg.isError}>{msg.content}</div>
          </div>
        {/each}
      {/if}

      {#if $sendingMessage}
        <div class="genie-message">
          <div class="genie-message-avatar"><i class="ph-fill ph-ticket"></i></div>
          <div class="genie-bubble typing"><i class="ph-bold ph-spinner animate-spin"></i> Genie is thinking...</div>
        </div>
      {/if}
    </div>

    <!-- Suggestions Bar -->
    {#if $suggestions.length > 0 && !$sendingMessage}
      <div class="genie-suggestions">
        {#each $suggestions as sug}
          <button class="genie-suggestion" on:click={() => handleSend(sug)}>{sug}</button>
        {/each}
      </div>
    {/if}

    <!-- Input Bar -->
    <div class="genie-input-area">
      <input
        type="text"
        placeholder="Ask Genie AI a question..."
        bind:value={userMessage}
        on:keydown={(e) => e.key === 'Enter' && handleSend()}
        disabled={$sendingMessage}
      />
      <button on:click={() => handleSend()} disabled={$sendingMessage}>
        <i class="ph-bold ph-paper-plane-right"></i>
      </button>
    </div>

    <div class="genie-disclaimer" role="note">
      Genie uses artificial intelligence and may provide inaccurate or incomplete information. Verify important details before acting.
    </div>
  </div>
{/if}

<style>
  .genie-container {
    position: fixed;
    bottom: 28px;
    right: 28px;
    z-index: 1000;
  }

  .genie-button {
    height: 48px;
    padding: 0 20px;
    border: none;
    border-radius: 24px;
    background: #2b1b38;
    color: white;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.92rem;
    font-weight: 700;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .genie-button:hover {
    background: #4f46e5;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(79, 70, 229, 0.4);
  }

  .genie-button i {
    font-size: 1.2rem;
    color: #facc15;
  }

  .genie-chat {
    position: fixed;
    right: 28px;
    bottom: 88px;
    width: 380px;
    height: 520px;
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 16px;
    box-shadow: 0 20px 45px rgba(43, 27, 54, 0.25);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 999;
  }

  .genie-chat-header {
    height: 68px;
    padding: 0 18px;
    background: #2b1b38;
    color: white;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }

  .genie-header-info {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .genie-avatar {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #facc15;
    font-size: 1.2rem;
  }

  .genie-header-info h4 {
    font-size: 0.95rem;
    font-weight: 700;
    margin: 0;
  }

  .status-indicator {
    font-size: 0.72rem;
    color: #a5b4fc;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .genie-status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.8);
  }

  .genie-close {
    width: 32px;
    height: 32px;
    border: none;
    background: transparent;
    color: #9ca3af;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .genie-close:hover {
    color: white;
    background: rgba(255, 255, 255, 0.15);
  }

  .genie-messages {
    flex: 1;
    overflow-y: auto;
    padding: 18px 16px;
    background: #f8fafc;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .genie-message {
    display: flex;
    gap: 10px;
  }

  .genie-message-avatar {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: #e0e7ff;
    color: #4f46e5;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 0.9rem;
  }

  .genie-bubble {
    max-width: 270px;
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 4px 12px 12px 12px;
    padding: 10px 14px;
    color: var(--text-main);
    font-size: 0.85rem;
    line-height: 1.45;
    box-shadow: var(--shadow-sm);
    /* Ticket status replies are multi-line (id/status/priority/etc, one
       per line) - preserve those line breaks instead of collapsing them
       into a single run-on line, while still wrapping long lines. */
    white-space: pre-line;
  }

  .genie-bubble.typing {
    color: var(--text-muted);
    font-style: italic;
  }

  .genie-bubble-error {
    border-color: #fecaca;
    background: #fef2f2;
    color: #b91c1c;
  }

  .genie-message-user {
    justify-content: flex-end;
  }

  .genie-message-user .genie-bubble {
    background: #4f46e5;
    color: white;
    border-color: #4f46e5;
    border-radius: 12px 4px 12px 12px;
  }

  .genie-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 0 16px 10px;
    background: #f8fafc;
  }

  .genie-suggestion {
    border: 1px solid #c7d2fe;
    background: white;
    color: #4f46e5;
    border-radius: 16px;
    padding: 5px 12px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }

  .genie-suggestion:hover {
    background: #eef2ff;
    border-color: #818cf8;
  }

  .genie-input-area {
    padding: 12px 16px;
    border-top: 1px solid var(--border-color);
    background: white;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .genie-input-area input {
    flex: 1;
    height: 38px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 0 12px;
    font-size: 0.85rem;
    outline: none;
  }

  .genie-input-area input:focus {
    border-color: var(--primary);
  }

  .genie-input-area button {
    width: 38px;
    height: 38px;
    flex-shrink: 0;
    border: none;
    border-radius: 8px;
    background: var(--primary);
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }

  .genie-input-area button:hover {
    background: var(--primary-hover);
  }

  .genie-disclaimer {
    padding: 6px 12px 10px;
    background: white;
    color: var(--text-muted);
    text-align: center;
    font-size: 0.68rem;
  }
</style>
