import { writable, get } from 'svelte/store';
import { apiExportGenieConversationPDF, apiFetchGenieConversations, apiFetchGenieConversation, apiGenieChat } from '../api.js';
import { userStore, isTicketer, isAdmin, isSuperAdmin } from './auth.js';
import { activeTab, genieDraftStore, onboardingDraftStore, refreshTicketState } from './tickets.js';

// Backend (services/conversation_service.py) is the source of truth - these
// stores mirror what's already persisted, they are never treated as the
// persistence layer themselves.
//
// This module is the ONE place both chat surfaces - the floating popup
// (GenieAgentWidget.svelte) and the full-page workspace (GenieAIView.svelte)
// - read/write conversation state through. Neither owns its own history
// array, selected-conversation id, or API call: they both call the same
// sendMessage() below, so a message sent in one surface is immediately
// visible in the other (same store instances, no copying/syncing needed).
export const conversations = writable([]);
export const selectedConversationId = writable(null);
export const conversationMessages = writable([]);
export const loadingConversations = writable(false);
export const loadingMessages = writable(false);
export const sendingMessage = writable(false);
export const searchQuery = writable('');

const DEFAULT_SUGGESTIONS = ['Check my tickets', 'VPN Setup Guide', 'Leave Balance Policy', 'IT Support Request'];
export const suggestions = writable(DEFAULT_SUGGESTIONS);

// Continuation state echoed back to the backend each turn, same contract
// GenieAgentWidget used to track locally (see models/chatbot.ChatRequest).
let activeIntent = null;
let activeRequestType = null;
let pendingAction = null;
let draft = null;
let onboardingDraft = null;

const GENIE_DRAFTING_INTENTS = ['create_ticket', 'support_issue', 'leave_management', 'start_onboarding'];

export async function loadConversations() {
  loadingConversations.set(true);
  try {
    const data = await apiFetchGenieConversations();
    conversations.set(data || []);
  } catch (err) {
    console.error('Failed to load Genie conversations:', err);
    conversations.set([]);
  } finally {
    loadingConversations.set(false);
  }
}

export function startNewChat() {
  selectedConversationId.set(null);
  conversationMessages.set([]);
  suggestions.set(DEFAULT_SUGGESTIONS);
  activeIntent = null;
  activeRequestType = null;
  pendingAction = null;
  draft = null;
  onboardingDraft = null;
}

export async function openConversation(conversationId) {
  loadingMessages.set(true);
  try {
    const data = await apiFetchGenieConversation(conversationId);
    if (!data) {
      throw new Error('Conversation not found');
    }
    selectedConversationId.set(data.id);
    conversationMessages.set(
      data.messages.map((m) => ({ role: m.role, content: m.content }))
    );
    suggestions.set(DEFAULT_SUGGESTIONS);
    activeIntent = null;
    activeRequestType = null;
    pendingAction = null;
    draft = null;
    onboardingDraft = null;
  } catch (err) {
    console.error('Failed to open Genie conversation:', err);
    throw err;
  } finally {
    loadingMessages.set(false);
  }
}

/**
 * Sends one user turn. History sent to the backend is built from the
 * messages already in conversationMessages - the message being sent right
 * now is never also duplicated into that history array (it only goes in
 * the `message` field of the request).
 */
export async function sendMessage(text) {
  const trimmed = (text || '').trim();
  if (!trimmed || get(sendingMessage)) return;

  const historyForRequest = get(conversationMessages).map((m) => ({
    role: m.role,
    message: m.content
  }));

  conversationMessages.update((msgs) => [...msgs, { role: 'user', content: trimmed }]);
  sendingMessage.set(true);

  try {
    const user = get(userStore);
    const res = await apiGenieChat(trimmed, {
      role: user?.role || 'Employee',
      history: historyForRequest,
      draft,
      onboarding_draft: onboardingDraft,
      active_intent: activeIntent,
      active_request_type: activeRequestType,
      pending_action: pendingAction,
      conversation_id: get(selectedConversationId)
    });

    const stillDrafting =
      res.intent && GENIE_DRAFTING_INTENTS.includes(res.intent) && !res.ready_for_review;
    activeIntent = stillDrafting ? res.intent : null;
    activeRequestType = stillDrafting ? res.request_type : null;
    draft = stillDrafting ? res.ticket_draft || null : null;
    onboardingDraft = stillDrafting ? res.onboarding_draft || null : null;
    pendingAction = res.pending_action || null;

    conversationMessages.update((msgs) => [
      ...msgs,
      { role: 'assistant', content: res.message || res.reply || '' }
    ]);

    if (res.suggestions && res.suggestions.length > 0) {
      suggestions.set(res.suggestions);
    }

    if (res.conversation_id) {
      selectedConversationId.set(res.conversation_id);
      loadConversations();
    }

    return res;
  } catch (err) {
    console.error('Genie sendMessage failed:', err);
    conversationMessages.update((msgs) => [
      ...msgs,
      {
        role: 'assistant',
        content: 'I am experiencing network trouble connecting to the AI engine. Please try again.',
        isError: true
      }
    ]);
    throw err;
  } finally {
    sendingMessage.set(false);
  }
}

// Every activeTab value Genie may navigate to, and (where the live
// Sidebar.svelte gates the equivalent nav item) the same role predicate
// Sidebar itself uses - kept in exact sync with the backend's
// NavigationTarget -> activeTab map in services/chatbot_service.py.
// Lives here (not in either chat surface) so both share one whitelist.
const NAV_TAB_ROLE_GATE = {
  knowledge: isTicketer,
  inbox: isTicketer,
  analytics: isTicketer,
  settings: isAdmin,
  onboarding: isSuperAdmin
};
const NAV_TABS = new Set([
  'dashboard',
  'create-ticket',
  'knowledge',
  'notifications',
  'announcements',
  'profile',
  ...Object.keys(NAV_TAB_ROLE_GATE)
]);

/**
 * Applies the structured, machine-actionable parts of a ChatResponse
 * (navigation, ticket-draft handoff, ready_for_review) exactly once,
 * regardless of which chat surface triggered sendMessage(). Both
 * GenieAgentWidget.svelte and GenieAIView.svelte call this with the value
 * sendMessage() returned - neither re-implements this logic itself.
 */
export function applyGenieResponseActions(res) {
  if (!res) return;

  if (res.action && res.action.type === 'navigate') {
    const target = res.action.target || '';
    const roleGate = NAV_TAB_ROLE_GATE[target];
    if (NAV_TABS.has(target) && (!roleGate || roleGate(get(userStore)))) {
      activeTab.set(target);
    }
  }

  if (res.action && res.action.type === 'export_conversation_pdf') {
    const conversationId = get(selectedConversationId);
    if (conversationId) {
      apiExportGenieConversationPDF(conversationId).catch((err) => {
        console.error('Failed to export Genie conversation:', err);
      });
    }
  }

  if (res.action && res.action.type === 'refresh_ticket') {
    refreshTicketState(res.action.ticket_id || null).catch((err) => {
      console.error('Failed to refresh tickets after Genie update:', err);
    });
  }

  if (res.ticket_draft || res.ready_for_review) {
    if (res.ticket_draft) {
      // res.request_type is a sibling field on the chat response, not part
      // of ticket_draft itself (models.chatbot.TicketDraft has no
      // request_type - see its docstring), so it must be merged in here or
      // CreateTicketView has no way to know which tab/form this draft
      // belongs to and silently falls back to Standard.
      genieDraftStore.set({ ...res.ticket_draft, request_type: res.request_type });
    }
    if (res.ready_for_review) {
      activeTab.set('create-ticket');
    }
  }

  if (res.onboarding_draft) {
    onboardingDraftStore.set(res.onboarding_draft);
    if (res.ready_for_review) activeTab.set('onboarding');
  }
}
