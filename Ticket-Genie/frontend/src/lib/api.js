const API_BASE_URL = "/api";

function getAuthHeaders() {
  let idToken = "";
  try {
    const stored = sessionStorage.getItem("portalUser") || sessionStorage.getItem("azureUser");
    if (stored) {
      const parsed = JSON.parse(stored);
      idToken = parsed.idToken || parsed.id_token || "";
    }
  } catch (e) {}

  const headers = { "Content-Type": "application/json" };
  if (idToken) {
    headers["Authorization"] = `Bearer ${idToken}`;
  }
  return headers;
}

/** ==================== TICKETS API ==================== */

export async function apiFetchTickets(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.search) query.append("search", params.search);
    if (params.status && params.status !== "all") query.append("status", params.status);
    if (params.priority && params.priority !== "all") query.append("priority", params.priority);
    if (params.department) query.append("department", params.department);
    if (params.adminView) query.append("admin_view", "true");

    const res = await fetch(`${API_BASE_URL}/tickets?${query.toString()}`, {
      headers: getAuthHeaders()
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) return data;
    }
  } catch (err) {
    console.warn("apiFetchTickets failed:", err);
  }
  return [];
}

export async function apiCreateTicket(payload) {
  const res = await fetch(`${API_BASE_URL}/tickets`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    let detail = `Ticket creation failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (e) {}
    throw new Error(detail);
  }
  return await res.json();
}

export async function apiUpdateTicket(ticketId, updateData) {
  const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(updateData)
  });
  if (!res.ok) {
    throw new Error(`Failed to update ticket (${res.status})`);
  }
  return await res.json();
}

export async function apiDeleteTicket(ticketId) {
  const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to delete ticket (${res.status})`);
  return await res.json();
}

export async function apiFetchComments(ticketId) {
  try {
    const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/comments`, {
      headers: getAuthHeaders()
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("apiFetchComments failed:", err);
  }
  return [];
}

export async function apiPostComment(ticketId, message) {
  const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/comments`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ message })
  });
  if (!res.ok) throw new Error("Failed to post comment");
  return await res.json();
}

export async function apiSuggestResponse(ticketId) {
  const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/suggested-response`, {
    method: "POST",
    headers: getAuthHeaders()
  });
  if (!res.ok) {
    let detail = `Failed to generate AI response (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (e) {}
    throw new Error(detail);
  }
  return await res.json();
}

/** ==================== EXPORT & CALENDAR API ==================== */

export async function apiExportTicketPDF(ticketId) {
  if (!ticketId) return;
  try {
    const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/export?format=pdf`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to export PDF (${res.status})`);
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = `Ticket_${ticketId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000);
  } catch (err) {
    console.error("apiExportTicketPDF error:", err);
    alert(err.message || "Failed to download PDF.");
  }
}

export async function apiExportTicketDOCX(ticketId) {
  if (!ticketId) return;
  try {
    const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/export?format=docx`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error(`Failed to export DOCX (${res.status})`);
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = `Ticket_${ticketId}.docx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000);
  } catch (err) {
    console.error("apiExportTicketDOCX error:", err);
    alert(err.message || "Failed to download DOCX.");
  }
}

/** ==================== KNOWLEDGE BASE API ==================== */

export async function apiListKnowledgeDocuments() {
  const res = await fetch('/api/knowledge/documents', { headers: getAuthHeaders() });
  if (!res.ok) throw new Error(`Unable to load knowledge documents (${res.status})`);
  return await res.json();
}

export async function apiUploadKnowledgeDocument({ title, category, file }) {
  const body = new FormData();
  body.append('title', title);
  body.append('category', category);
  body.append('file', file);
  const headers = getAuthHeaders();
  delete headers['Content-Type'];
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  let res;
  try {
    res = await fetch('/api/knowledge/documents', {
      method: "POST",
      headers,
      body,
      signal: controller.signal
    });
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Document processing exceeded 60 seconds. Nothing was confirmed as indexed; please try again.');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || `Document upload failed (${res.status})`);
  }
  return await res.json();
}

/** ==================== ADMIN & RBAC API ==================== */

export async function apiFetchDepartments() {
  try {
    const res = await fetch("/api/admin/departments", { headers: getAuthHeaders() });
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("apiFetchDepartments failed:", err);
  }
  return [];
}

export async function apiFetchDepartmentUsers(departmentName = null) {
  try {
    const query = departmentName ? `?department_name=${encodeURIComponent(departmentName)}` : "";
    const res = await fetch(`/api/admin/departments/users${query}`, { headers: getAuthHeaders() });
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("apiFetchDepartmentUsers failed:", err);
  }
  return [];
}

export async function apiAssignDepartmentUser(payload) {
  const res = await fetch("/api/admin/departments/users", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Role assignment failed (${res.status})`);
  return await res.json();
}

export async function apiRemoveDepartmentUser(departmentName, azureObjectId) {
  const res = await fetch(`/api/admin/departments/users?department_name=${encodeURIComponent(departmentName)}&azure_object_id=${encodeURIComponent(azureObjectId)}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to remove department user mapping (${res.status})`);
  return await res.json();
}

export async function apiCreateDepartment(name, queueName, description = "") {
  const res = await fetch("/api/admin/departments", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ name, queue_name: queueName, description })
  });
  if (!res.ok) throw new Error(`Department creation failed (${res.status})`);
  return await res.json();
}

/** ==================== AI GENIE AGENT API ==================== */

export async function apiGenieChat(message, state = {}) {
  try {
    const payload = {
      message,
      role: state.role || "Employee",
      history: state.history || [],
      draft: state.draft || null,
      onboarding_draft: state.onboarding_draft || state.onboardingDraft || null,
      active_intent: state.active_intent || state.activeIntent || null,
      active_request_type: state.active_request_type || state.activeRequestType || null,
      pending_action: state.pending_action || state.pendingAction || null,
      conversation_id: state.conversation_id || state.conversationId || null
    };

    const res = await fetch("/api/chatbot/message", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const data = await res.json();
      return {
        reply: data.message || "I am Genie, your AI helpdesk assistant.",
        message: data.message || "I am Genie, your AI helpdesk assistant.",
        suggestions: data.suggestions || ["Ask a question", "Help me create a ticket", "Check my ticket status"],
        action: data.action || null,
        ticket_draft: data.ticket_draft || null,
        onboarding_draft: data.onboarding_draft || null,
        request_type: data.request_type || null,
        missing_fields: data.missing_fields || [],
        ready_for_review: data.ready_for_review || false,
        intent: data.intent || null,
        pending_action: data.pending_action || null,
        ticket_candidates: data.ticket_candidates || [],
        conversation_id: data.conversation_id || null
      };
    }
  } catch (e) {
    console.warn("api/chatbot/message call error, falling back to /api/genie/chat:", e);
  }

  try {
    const res = await fetch("/api/genie/chat", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ message })
    });
    if (res.ok) {
      const data = await res.json();
      return {
        reply: data.reply || data.message || "I am Genie, your AI helpdesk assistant.",
        message: data.reply || data.message || "I am Genie, your AI helpdesk assistant.",
        suggestions: data.suggestions || ["Check my tickets", "IT Help"],
        action: data.action || null,
        ticket_draft: data.ticket_draft || null,
        onboarding_draft: data.onboarding_draft || null,
        request_type: data.request_type || null,
        missing_fields: data.missing_fields || [],
        ready_for_review: data.ready_for_review || false,
        intent: data.intent || null,
        pending_action: null,
        ticket_candidates: [],
        conversation_id: null
      };
    }
  } catch (err) {
    console.error("apiGenieChat fallback failed:", err);
  }

  return {
    reply: "I am Genie, your AI support agent. I can assist you with ticket status, IT troubleshooting, and corporate policies.",
    message: "I am Genie, your AI support agent. I can assist you with ticket status, IT troubleshooting, and corporate policies.",
    suggestions: ["Check my tickets", "IT Help", "Time Off Policy"],
    action: null,
    ticket_draft: null,
    request_type: null,
    missing_fields: [],
    ready_for_review: false,
    intent: null,
    pending_action: null,
    ticket_candidates: [],
    conversation_id: null
  };
}

export async function apiFetchGenieConversations() {
  try {
    const res = await fetch(`${API_BASE_URL}/chatbot/conversations`, {
      headers: getAuthHeaders()
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) return data;
    }
  } catch (err) {
    console.warn("apiFetchGenieConversations failed:", err);
  }
  return [];
}

export async function apiFetchGenieConversation(conversationId) {
  try {
    const res = await fetch(`${API_BASE_URL}/chatbot/conversations/${encodeURIComponent(conversationId)}`, {
      headers: getAuthHeaders()
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("apiFetchGenieConversation failed:", err);
  }
  return null;
}

export async function apiExportGenieConversationPDF(conversationId) {
  if (!conversationId) throw new Error("Select a saved conversation first.");
  const res = await fetch(
    `${API_BASE_URL}/chatbot/conversations/${encodeURIComponent(conversationId)}/export`,
    { headers: getAuthHeaders() }
  );
  if (!res.ok) throw new Error(`Failed to export conversation PDF (${res.status})`);

  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = `Genie_Conversation_${conversationId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000);
}

/** ==================== USER PROFILE & ANNOUNCEMENTS ==================== */

export async function apiFetchNotifications() {
  const res = await fetch(`${API_BASE_URL}/notifications`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Unable to load notifications (${res.status})`);
  return await res.json();
}

export async function apiMarkNotificationRead(notificationId) {
  const res = await fetch(
    `${API_BASE_URL}/notifications/${encodeURIComponent(notificationId)}/read`,
    { method: "PUT", headers: getAuthHeaders() }
  );
  if (!res.ok) throw new Error(`Unable to mark notification as read (${res.status})`);
  return await res.json();
}

export async function apiFetchAnnouncements() {
  try {
    const res = await fetch(`${API_BASE_URL}/announcements`, { headers: getAuthHeaders() });
    if (res.ok) return await res.json();
  } catch (err) {
    console.error("apiFetchAnnouncements failed:", err);
  }
  return [];
}

export async function apiFetchDepartmentHealth(department = null) {
  const query = department ? `?department=${encodeURIComponent(department)}` : "";
  const res = await fetch(`${API_BASE_URL}/analytics/department-health${query}`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) {
    let detail = `Unable to load department analytics (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return await res.json();
}

export async function apiFetchAIUsage(days = 30) {
  const res = await fetch(`${API_BASE_URL}/analytics/ai-usage?days=${encodeURIComponent(days)}`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) {
    let detail = `Unable to load Azure AI usage (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

export async function apiFetchAISettings() {
  try {
    const res = await fetch(`${API_BASE_URL}/admin/ai-settings`, {
      headers: getAuthHeaders()
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("apiFetchAISettings failed:", err);
  }
  return {
    primary_model: "gpt-5.2",
    fallback_model: "gpt-4o-mini",
    temperature: 0.2,
    max_tokens: 4096,
    confidence_threshold: 0.70,
    top_k_chunks: 3,
    similarity_threshold: 0.75,
    monthly_budget_usd: 50.0,
    telemetry_level: "verbose",
    feature_auto_triage: true,
    feature_chatbot_genie: true,
    feature_suggested_responses: true,
    feature_rag_grounding: true,
    feature_sla_scoring: true,
    feature_issue_clustering: true
  };
}

export async function apiSaveAISettings(settingsPayload) {
  const res = await fetch(`${API_BASE_URL}/admin/ai-settings`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(settingsPayload)
  });
  if (!res.ok) {
    let detail = `Failed to save AI settings (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return await res.json();
}


export async function apiCreateAnnouncement(payload) {
  const res = await fetch(`${API_BASE_URL}/announcements`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    let detail = `Unable to create announcement (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return await res.json();
}

export async function apiDeleteAnnouncement(announcementId) {
  const res = await fetch(`${API_BASE_URL}/announcements/${encodeURIComponent(announcementId)}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
  if (!res.ok) {
    let detail = `Unable to delete announcement (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return await res.json();
}

export async function apiCheckAnnouncementMatch(title, description = "") {
  const res = await fetch(`${API_BASE_URL}/announcements/match`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ title, description })
  });
  if (!res.ok) throw new Error(`Announcement check failed (${res.status})`);
  return await res.json();
}

export async function apiFetchUserProfile() {
  try {
    const res = await fetch(`${API_BASE_URL}/users/profile`, { headers: getAuthHeaders() });
    if (res.ok) return await res.json();
  } catch (err) {
    console.error("apiFetchUserProfile failed:", err);
  }
  return { name: "User", email: "user@ticketgenie.com", role: "Employee", department: "Operations" };
}

export async function apiFetchUpperManagementUsers() {
  try {
    const res = await fetch(`${API_BASE_URL}/users/upper-management`, { headers: getAuthHeaders() });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) return data;
    }
  } catch (err) {
    console.warn("apiFetchUpperManagementUsers failed:", err);
  }
  return [
    { name: "Greg Davis", role: "Admin & VP Operations", department: "Upper Executive Management" },
    { name: "Sarah Jenkins", role: "Director of HR & Operations", department: "Upper Management" },
    { name: "Alex Vance", role: "Chief Operations Officer", department: "Upper Management" }
  ];
}

/** ==================== ONBOARDING PIPELINE ==================== */

async function onboardingRequest(path = "", options = {}) {
  const res = await fetch(`${API_BASE_URL}/onboarding${path}`, {
    ...options,
    headers: getAuthHeaders()
  });
  if (!res.ok) {
    let detail = `Onboarding request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (e) {}
    throw new Error(detail);
  }
  return await res.json();
}

export function apiFetchOnboardingCases() {
  return onboardingRequest();
}

export function apiFetchOnboardingCase(onboardingId) {
  return onboardingRequest(`/${encodeURIComponent(onboardingId)}`);
}

export function apiSuggestOnboardingPlan(jobTitle, startDate) {
  return onboardingRequest("/suggest", {
    method: "POST",
    body: JSON.stringify({ job_title: jobTitle, start_date: startDate })
  });
}

export function apiStartOnboarding(payload) {
  return onboardingRequest("/start", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function apiAddOnboardingTicket(onboardingId, payload) {
  return onboardingRequest(`/${encodeURIComponent(onboardingId)}/tickets`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function apiFetchLatestAnnouncementWithSeverity(signal = null) {
  try {
    const options = { headers: getAuthHeaders() };
    if (signal) {
      options.signal = signal;
    }
    const res = await fetch(`${API_BASE_URL}/announcements/latest`, options);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    if (err?.name !== "AbortError") {
      console.warn("apiFetchLatestAnnouncementWithSeverity failed:", err);
    }
  }
  return { announcement: null, severity: null };
}

export async function apiClassifyAnnouncementSeverity(payload) {
  try {
    const res = await fetch(`${API_BASE_URL}/announcements/severity`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("apiClassifyAnnouncementSeverity failed:", err);
  }
  return {
    level: "info",
    label: "ANNOUNCEMENT",
    color_class: "severity-info",
    icon: "ph-megaphone"
  };
}

export async function apiFetchPromptCacheStats() {
  try {
    const res = await fetch(`${API_BASE_URL}/admin/prompt-cache/stats`, {
      headers: getAuthHeaders()
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("apiFetchPromptCacheStats failed:", err);
  }
  return {
    active_items: 0,
    hits: 0,
    misses: 0,
    total_lookups: 0,
    hit_rate_pct: 0,
    tokens_saved: 0,
    cost_saved_usd: 0,
    per_agent: {}
  };
}

export async function apiPurgePromptCache() {
  const res = await fetch(`${API_BASE_URL}/admin/prompt-cache/purge`, {
    method: "POST",
    headers: getAuthHeaders()
  });
  if (!res.ok) {
    throw new Error(`Failed to purge prompt cache (${res.status})`);
  }
  return await res.json();
}

