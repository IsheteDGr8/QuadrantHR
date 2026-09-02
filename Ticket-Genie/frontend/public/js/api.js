(function patchFetchForBearerToken() {
    if (window._bearerFetchPatched) return;
    window._bearerFetchPatched = true;
    const originalFetch = window.fetch;

    window.fetch = function (resource, options = {}) {
        const url = typeof resource === "string" ? resource : resource?.url || "";

        // Inject Authorization Bearer header into all backend /api/ requests
        if (url.includes("/api/") && !url.includes("/api/config")) {
            let idToken = "";
            try {
                const stored = sessionStorage.getItem("azureUser") || sessionStorage.getItem("portalUser") || localStorage.getItem("azureUser") || localStorage.getItem("portalUser");
                if (stored) {
                    const parsed = JSON.parse(stored);
                    idToken = parsed.idToken || parsed.id_token || "";
                }
            } catch (e) { }

            if (idToken) {
                const bearerHeader = `Bearer ${idToken}`;

                if (typeof resource === "object" && resource instanceof Request) {
                    if (!resource.headers.has("Authorization")) {
                        resource.headers.set("Authorization", bearerHeader);
                    }
                }

                options = options || {};
                let headers = options.headers || {};

                if (headers instanceof Headers) {
                    if (!headers.has("Authorization")) {
                        headers.set("Authorization", bearerHeader);
                    }
                } else if (Array.isArray(headers)) {
                    const hasAuth = headers.some(([k]) => k.toLowerCase() === "authorization");
                    if (!hasAuth) {
                        headers.push(["Authorization", bearerHeader]);
                    }
                } else {
                    headers = { ...headers };
                    if (!headers["Authorization"] && !headers["authorization"]) {
                        headers["Authorization"] = bearerHeader;
                    }
                }
                options.headers = headers;
            }
        }

        return originalFetch.call(this, resource, options);
    };
})();

const API_BASE_URL = window.API_BASE_URL || "/api";

async function apiFetchTickets(params = {}) {
    try {
        if (window.AzureAuth?.ready) {
            await window.AzureAuth.ready;
        }
        const query = new URLSearchParams();
        if (params.search) query.append("search", params.search);
        if (params.status && params.status !== "all") query.append("status", params.status);
        if (params.priority && params.priority !== "all") query.append("priority", params.priority);
        if (params.department) query.append("department", params.department);
        if (params.requesterId) query.append("requester_id", params.requesterId);
        if (params.adminView) query.append("admin_view", "true");

        const res = await fetch(`${API_BASE_URL}/tickets?${query.toString()}`);
        if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data)) return data;
        }
    } catch (err) {
        console.warn("apiFetchTickets failed:", err);
    }
    return [];
}

async function apiFetchTicket(ticketId) {
    const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}`);
    if (!res.ok) {
        let detail = `Unable to load ticket (HTTP ${res.status})`;
        try {
            const body = await res.json();
            if (body.detail) detail = body.detail;
        } catch (e) {}
        throw new Error(detail);
    }
    return await res.json();
}

async function apiCreateTicket(ticketPayload) {
    const res = await fetch(`${API_BASE_URL}/tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ticketPayload)
    });

    if (!res.ok) {
        let detail = `Ticket creation failed (HTTP ${res.status})`;
        try {
            const body = await res.json();
            if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        } catch (e) {}
        throw new Error(detail);
    }

    return await res.json();
}

async function apiCheckAnnouncementMatch(title, description = "") {
    const res = await fetch(`${API_BASE_URL}/announcements/match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, description })
    });

    if (!res.ok) {
        throw new Error(`Announcement check failed (HTTP ${res.status})`);
    }

    return await res.json();
}

async function apiUpdateTicket(ticketId, ticketUpdate) {
    try {
        const res = await fetch(`${API_BASE_URL}/tickets/${ticketId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(ticketUpdate)
        });
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiUpdateTicket failed:", err);
    }
    return null;
}

async function apiGetComments(ticketId) {
    const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/comments`);
    if (!res.ok) throw new Error(`Unable to load conversation (HTTP ${res.status})`);
    return await res.json();
}

async function apiPostComment(ticketId, message, senderRole = "Employee") {
    const res = await fetch(`${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, sender_role: senderRole }),
    });
    if (!res.ok) throw new Error(`Unable to send message (HTTP ${res.status})`);
    return await res.json();
}

async function apiSuggestTicketResponse(ticketId) {
    const res = await fetch(
        `${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/suggested-response`,
        { method: "POST" }
    );
    if (!res.ok) {
        let detail = `Unable to suggest a response (HTTP ${res.status})`;
        try {
            const body = await res.json();
            if (body.detail) detail = body.detail;
        } catch (e) {}
        throw new Error(detail);
    }
    return await res.json();
}

async function apiFetchAnnouncements() {
    try {
        const res = await fetch(`${API_BASE_URL}/announcements`);
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiFetchAnnouncements failed:", err);
    }
    return [];
}

async function apiCreateAnnouncement(payload) {
    try {
        const res = await fetch(`${API_BASE_URL}/announcements`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiCreateAnnouncement failed:", err);
    }
    return null;
}

async function apiDeleteAnnouncement(ancId) {
    try {
        const res = await fetch(`${API_BASE_URL}/announcements/${ancId}`, { method: "DELETE" });
        return res.ok;
    } catch (err) {
        console.error("apiDeleteAnnouncement failed:", err);
    }
    return false;
}

async function apiFetchNotifications() {
    try {
        const res = await fetch(`${API_BASE_URL}/notifications`);
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiFetchNotifications failed:", err);
    }
    return [];
}

async function apiMarkNotificationRead(notifId) {
    try {
        const res = await fetch(`${API_BASE_URL}/notifications/${notifId}/read`, { method: "PUT" });
        return res.ok;
    } catch (err) {
        console.error("apiMarkNotificationRead failed:", err);
    }
    return false;
}

async function apiFetchOnboarding() {
    try {
        const res = await fetch(`${API_BASE_URL}/onboarding`);
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiFetchOnboarding failed:", err);
    }
    return [
        { id: "onb-101", employee_name: "Aarav Sharma", role: "Senior Software Engineer", department: "IT Engineering", visa_status: "H-1B Active", start_date: "2026-09-01", status: "Completed" },
        { id: "onb-102", employee_name: "Elena Rostova", role: "Product Designer", department: "UX Design", visa_status: "OPT STEM", start_date: "2026-09-15", status: "In Progress" },
        { id: "onb-103", employee_name: "Marcus Vance", role: "Data Analyst", department: "HR Analytics", visa_status: "TN Visa", start_date: "2026-10-01", status: "Pending Documents" }
    ];
}

async function apiCreateOnboarding(payload) {
    try {
        const res = await fetch(`${API_BASE_URL}/onboarding`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiCreateOnboarding failed:", err);
    }
    return null;
}

async function apiUpdateOnboardingStatus(recId, status) {
    try {
        const res = await fetch(`${API_BASE_URL}/onboarding/${recId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status })
        });
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiUpdateOnboardingStatus failed:", err);
    }
    return null;
}

async function apiFetchUserProfile() {
    try {
        console.log(`[API Request] Executing fetch: ${API_BASE_URL}/users/profile`);
        const res = await fetch(`${API_BASE_URL}/users/profile`);
        console.log(`[API Response] Status: ${res.status} ${res.statusText}`);
        if (res.ok) {
            const data = await res.json();
            console.log("[API Data] Profile payload:", data);
            return data;
        }
    } catch (err) {
        console.error("apiFetchUserProfile failed:", err);
    }
    return { name: "Nishita", email: "nishita@ticketgenie.com", role: "Employee", department: "HR & Operations", phone: "+1 (555) 019-2834" };
}

async function apiUpdateUserProfile(payload) {
    try {
        const res = await fetch(`${API_BASE_URL}/users/profile`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiUpdateUserProfile failed:", err);
    }
    return null;
}

async function apiGenieChat(message) {
    try {
        const res = await fetch(`${API_BASE_URL}/genie/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        });
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("apiGenieChat failed:", err);
    }
    return { reply: "I'm having trouble connecting to the backend right now. Please try again shortly.", suggestions: ["Check my tickets"] };
}

async function apiRunReAct(message, role = "Super Admin") {
    try {
        const res = await fetch(`${API_BASE_URL}/genie/react`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, role }),
        });
        return await res.json();
    } catch (err) {
        console.error("apiRunReAct failed:", err);
        return { reply: "ReAct Agent Engine execution failed. Check backend connection." };
    }
}

async function apiRunExecAction(command) {
    try {
        const res = await fetch(`${API_BASE_URL}/genie/exec-agent`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command }),
        });
        return await res.json();
    } catch (err) {
        console.error("apiRunExecAction failed:", err);
        return { executive_response: "Executive command execution failed." };
    }
}

function getExportUrl(ticketId, format = "pdf") {
    return `${API_BASE_URL}/tickets/${ticketId}/export?format=${format}`;
}

async function apiDownloadTicketDocument(ticketId, format = "pdf") {
    const safeFormat = format === "docx" ? "docx" : "pdf";
    const res = await fetch(
        `${API_BASE_URL}/tickets/${encodeURIComponent(ticketId)}/export?format=${safeFormat}`
    );
    if (!res.ok) throw new Error(`Unable to export ticket (HTTP ${res.status})`);

    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `ticket_${ticketId}.${safeFormat}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
}

// Bind API client functions globally to window
Object.assign(window, {
    API_BASE_URL,
    apiFetchTickets,
    apiFetchTicket,
    apiCreateTicket,
    apiUpdateTicket,
    apiGetComments,
    apiPostComment,
    apiSuggestTicketResponse,
    apiFetchAnnouncements,
    apiCreateAnnouncement,
    apiDeleteAnnouncement,
    apiFetchNotifications,
    apiMarkNotificationRead,
    apiFetchOnboarding,
    apiCreateOnboarding,
    apiUpdateOnboardingStatus,
    apiFetchUserProfile,
    apiUpdateUserProfile,
    apiGenieChat,
    apiRunReAct,
    apiRunExecAction,
    apiDownloadTicketDocument,
    getExportUrl
});
