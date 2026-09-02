// Client for the mini chat widget. No auth headers here on purpose — the
// widget renders on the public Landing page (no signed-in user yet) as
// well as every dashboard, and the real backend endpoint below has no
// auth dependency to match.
//
// "What does this screen do?" is answered locally first, from
// screenKnowledgeBase.js, without a network call — that keeps the answer
// instant and exact instead of leaving it to the LLM to guess at a page
// it's never seen. Anything else falls through to the real backend,
// POST /chat (see backend/chat_agent.py).
//
// Theme-switching and page navigation are genuinely agentic: whether a
// message means "change the theme" or "go to X" is decided by an LLM
// call (POST /chat/intent, see backend/chat_agent.py's
// interpret_chat_intent), not a fixed keyword/regex list — people phrase
// "make it dark" as "dark mode", "dark theme", "make it darker", "night
// mode"... a hardcoded pattern only ever covers the phrasings someone
// thought to test. This file only carries out whatever the LLM decided
// (flip prefs, call navigateTo) — it doesn't do the deciding itself.

import { BACKEND_URL } from "./backendConfig";
import { SCREENS, findScreen, getScreenById } from "./screenKnowledgeBase";
import { getPrefs, savePrefs } from "./store";
import { applyPrefs } from "../utils/applyPrefs";

const CURRENT_PAGE_PATTERN = /this (page|screen)|where am i/i;
const SCREEN_QUESTION_PATTERN = /what (is|does|'s)|explain|tell me about|describe/i;

async function classifyIntent(message) {
  try {
    const response = await fetch(`${BACKEND_URL}/chat/intent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        screens: SCREENS.map((s) => ({ id: s.id, name: s.name })),
      }),
    });

    if (!response.ok) return null;
    return await response.json();
  } catch {
    // Classification is a nice-to-have, not a hard dependency — if the
    // backend/network is unavailable, fall through to the existing
    // local screen-question handling and general chat below instead of
    // failing the whole message.
    return null;
  }
}

function formatScreenAnswer(screen) {
  const actions = screen.keyActions.map((a) => `• ${a}`).join("\n");
  return `**${screen.name}**\n${screen.purpose}\n\nWhat you can do here:\n${actions}`;
}

async function askBackend(message) {
  const response = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  const data = await response.json();
  return data.answer;
}

export async function askChatWidget(message, currentScreen, navigateTo) {
  const intent = await classifyIntent(message);

  if (intent?.intent === "set_theme" && intent.theme) {
    const updated = { ...getPrefs(), theme: intent.theme };
    savePrefs(updated);
    applyPrefs(updated);
    return `Done — switched to ${intent.theme} mode.`;
  }

  if (intent?.intent === "navigate" && intent.screen_id && navigateTo) {
    const target = getScreenById(intent.screen_id);
    if (target) {
      const moved = navigateTo(target.id);
      return moved
        ? `Taking you to ${target.name}.`
        : `${target.name} isn't reachable from here.`;
    }
  }

  const looksLikeScreenQuestion = SCREEN_QUESTION_PATTERN.test(message);

  if (CURRENT_PAGE_PATTERN.test(message) && currentScreen) {
    const screen = getScreenById(currentScreen);
    if (screen) return formatScreenAnswer(screen);
  }

  if (currentScreen && looksLikeScreenQuestion) {
    const own = getScreenById(currentScreen);
    if (own && [own.name, ...own.aliases].some((a) => message.toLowerCase().includes(a.toLowerCase()))) {
      return formatScreenAnswer(own);
    }
  }

  const matched = findScreen(message);
  if (matched) return formatScreenAnswer(matched);

  if (looksLikeScreenQuestion) {
    return "I don't have info on that screen yet — try asking about a specific page by name, or rephrase what you're looking for.";
  }

  return askBackend(message);
}
