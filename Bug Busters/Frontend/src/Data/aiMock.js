import { BACKEND_URL } from "./backendConfig";
import { getAuthHeader } from "./authToken";

// --------------------------------------------------
// Ask AI About Selected Policy Text
// --------------------------------------------------

export async function askAIAboutText(question, highlightedText) {
  const authHeader = await getAuthHeader();

  const response = await fetch(
    `${BACKEND_URL}/ask-ai`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authHeader || {}),
      },
      body: JSON.stringify({
        highlighted_text: highlightedText,
        question,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  const data = await response.json();

  return data.answer;
}


// --------------------------------------------------
// Reword Selected Policy Text
// --------------------------------------------------

export async function rewordText(instruction, highlightedText) {
  const authHeader = await getAuthHeader();

  const response = await fetch(
    `${BACKEND_URL}/refine-policy`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authHeader || {}),
      },
      body: JSON.stringify({
        current_policy: highlightedText,
        instruction,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  const data = await response.json();

  return data.policy;
}


// --------------------------------------------------
// Incident Report AI
// --------------------------------------------------

// The backend gives a specific, actionable detail message for some
// failures (e.g. a message flagged by the content safety filter) -
// surface that instead of a generic "Backend returned 422".
async function throwIncidentError(response) {
  let detail = null;

  try {
    detail = (await response.json())?.detail;
  } catch {
    // Response body wasn't JSON - fall through to the generic message.
  }

  throw new Error(detail || `Backend returned ${response.status}`);
}

export async function replyToIncidentMessage(conversationSoFar) {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/incident/reply`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authHeader || {}),
    },
    body: JSON.stringify({
      messages: conversationSoFar.map((m) => ({ role: m.role, text: m.text })),
    }),
  });

  if (!response.ok) {
    await throwIncidentError(response);
  }

  const data = await response.json();

  return data.reply;
}


// summarizeIncident and suggestIncidentNextSteps are always called
// together (see IncidentReport.jsx's handleGenerate) with the same
// conversation, and the backend already returns both in one response —
// this cache lets the second call reuse the first's in-flight request
// instead of firing a duplicate LLM call for the same result.
let cachedAnalysis = null; // { conversation, promise }

function getIncidentAnalysis(conversation) {
  if (cachedAnalysis && cachedAnalysis.conversation === conversation) {
    return cachedAnalysis.promise;
  }

  const promise = (async () => {
    const authHeader = await getAuthHeader();

    const response = await fetch(`${BACKEND_URL}/incident/summarize`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authHeader || {}),
      },
      body: JSON.stringify({
        messages: conversation.map((m) => ({ role: m.role, text: m.text })),
      }),
    });

    if (!response.ok) {
      await throwIncidentError(response);
    }

    return response.json();
  })();

  cachedAnalysis = { conversation, promise };

  return promise;
}

export async function summarizeIncident(conversation) {
  const data = await getIncidentAnalysis(conversation);
  return data.summary;
}


export async function suggestIncidentNextSteps(conversation) {
  const data = await getIncidentAnalysis(conversation);
  return data.next_steps;
}