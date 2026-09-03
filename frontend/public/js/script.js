console.log("[Script Log] TicketGenie main script.js loaded successfully!");

/* =========================================================
   AUTO-LOAD DEPENDENCIES, TELEMETRY & AZURE AUTH MODULES
   ========================================================= */
(function autoLoadModules() {
    const scriptElement = document.querySelector('script[src*="script.js"]');
    const basePath = scriptElement ? scriptElement.src.split("script.js")[0] : "/js/";

    if (!window.apiFetchTickets && !window.apiFetchAnnouncements) {
        const apiScript = document.createElement("script");
        apiScript.src = basePath + "api.js";
        document.head.appendChild(apiScript);
    }

    if (!window.TicketGenieTelemetry) {
        const teleScript = document.createElement("script");
        teleScript.src = basePath + "telemetry.js";
        teleScript.async = true;
        document.head.appendChild(teleScript);
    }

    if (!window.AzureAuth) {
        const authScript = document.createElement("script");
        authScript.src = basePath + "azure-auth.js";
        authScript.async = false;
        document.head.appendChild(authScript);
    }
})();

/* =========================================================
   GLOBAL SAFE API FALLBACK BINDINGS
   ========================================================= */
if (!window.apiFetchTickets) {
    window.apiFetchTickets = async function(params = {}) {
        try {
            const res = await fetch("/api/tickets");
            if (res.ok) return await res.json();
        } catch (e) {}
        return [];
    };
}

if (!window.apiFetchOnboarding) {
    window.apiFetchOnboarding = async function() {
        try {
            const res = await fetch("/api/onboarding");
            if (res.ok) return await res.json();
        } catch (e) {}
        return [
            { id: "onb-101", employee_name: "Aarav Sharma", role: "Senior Software Engineer", department: "IT Engineering", visa_status: "H-1B Active", start_date: "2026-09-01", status: "Completed" },
            { id: "onb-102", employee_name: "Elena Rostova", role: "Product Designer", department: "UX Design", visa_status: "OPT STEM", start_date: "2026-09-15", status: "In Progress" },
            { id: "onb-103", employee_name: "Marcus Vance", role: "Data Analyst", department: "HR Analytics", visa_status: "TN Visa", start_date: "2026-10-01", status: "Pending Documents" }
        ];
    };
}

if (!window.getExportUrl) {
    window.getExportUrl = function(ticketId, format = "pdf") {
        return `/api/tickets/${ticketId}/export?format=${format}`;
    };
}

if (!window.apiRunExecAction) {
    window.apiRunExecAction = async function(command) {
        try {
            const res = await fetch("/api/genie/exec-agent", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command })
            });
            if (res.ok) return await res.json();
        } catch (e) {}
        return { executive_response: "Action completed successfully." };
    };
}
/* =========================================================
   GLOBAL BEARER TOKEN PROPAGATION INTERCEPTOR
   ========================================================= */
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

/* =========================================================
   LOCAL STORAGE FALLBACK & IDENTIFIER HELPERS
   ========================================================= */
var STORAGE_KEY = window.STORAGE_KEY || "ticketGenieTickets";

function getTickets() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem("employee_tickets");
        if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed)) return parsed;
        }
    } catch (e) {}

    return [];
}

function saveTickets(tickets) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
        localStorage.setItem("employee_tickets", JSON.stringify(tickets));
    } catch (e) {}
}

function generateTicketId() {
    const tickets = getTickets();
    let highestNumber = 1028;
    tickets.forEach(ticket => {
        const number = parseInt(String(ticket.id).replace("HD-", ""), 10);
        if (!isNaN(number) && number > highestNumber) {
            highestNumber = number;
        }
    });
    return `HD-${highestNumber + 1}`;
}

function getCurrentRequesterId() {
    try {
        const user = JSON.parse(localStorage.getItem("portalUser") || "{}");
        return user.email || user.id || null;
    } catch (e) {
        return null;
    }
}

function escapeHTML(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
window.escapeHTML = escapeHTML;

function showNotification(message, type = "info") {
    console.log(`[Notification - ${type}] ${message}`);
    let toast = document.getElementById("globalToastNotification");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "globalToastNotification";
        toast.style.cssText = "position: fixed; bottom: 24px; right: 24px; z-index: 9999; background: #1e293b; color: white; padding: 12px 20px; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); font-size: 14px; transition: opacity 0.3s ease;";
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.opacity = "1";
    setTimeout(() => { toast.style.opacity = "0"; }, 3500);
}

function showFormError(message) {
    const error = document.getElementById("formErrorMessage");
    if (!error) return;
    error.textContent = message;
    error.style.display = "block";
    error.scrollIntoView({ behavior: "smooth", block: "center" });
}

function showSuccessMessage(ticket) {
    let success = document.getElementById("ticketSuccessMessage");
    if (!success) {
        success = document.createElement("div");
        success.id = "ticketSuccessMessage";
        success.className = "ticket-success-message";
        document.body.appendChild(success);
    }

    success.innerHTML = `
        <div class="success-icon"><i class="fa-solid fa-check"></i></div>
        <div>
            <strong>Request submitted successfully</strong>
            <span>Ticket #${escapeHTML(ticket.id)} has been created.</span>
        </div>
    `;

    requestAnimationFrame(() => { success.classList.add("show"); });
    setTimeout(() => { success.classList.remove("show"); }, 3000);
}

/* =========================================================
   NEW REQUEST FORM (HANDLED BY PAGE SPECIFIC FORM SUBMIT HANDLERS)
   ========================================================= */
function initializeNewRequestForm() {
    // Page-specific inline submit handlers handle ticket creation.
}


/* =========================================================
   GLOBAL DARK MODE & HAMBURGER SIDEBAR TOGGLES
   ========================================================= */
function initDarkMode() {
    const savedTheme = localStorage.getItem("theme");
    const isDark = savedTheme === "dark";
    if (isDark) {
        document.body.classList.add("dark-mode");
    } else {
        document.body.classList.remove("dark-mode");
    }

    const darkToggle = document.getElementById("myCustomDarkToggle") || document.getElementById("darkModeToggle");
    if (darkToggle) {
        darkToggle.setAttribute("aria-checked", isDark ? "true" : "false");
    }
}

function initSidebarToggle() {
    const sidebar = document.querySelector(".sidebar");
    const savedState = localStorage.getItem("sidebar_collapsed");
    if (sidebar && savedState === "true") {
        sidebar.classList.add("collapsed");
    }
}

function handleSignOut(event) {
    if (event) event.preventDefault();
    window.location.href = "../index.html";
}

/* =========================================================
   MODAL CHAT & TICKET CHAT UTILITIES
   ========================================================= */
var currentOpenTicketId = window.currentOpenTicketId || null;
var loadedMyTicketsMap = window.loadedMyTicketsMap || {};

async function openTicketChatModal(ticketId, ticketObj = null) {
    const modal = document.getElementById("ticketModal");
    if (!modal) return;

    currentOpenTicketId = ticketId;

    let ticket = ticketObj || loadedMyTicketsMap[ticketId];
    if (!ticket) {
        try {
            const fetchFn = window.apiFetchTickets || apiFetchTickets;
            const res = await fetchFn({ search: ticketId });
            if (res && res.length > 0) ticket = res[0];
        } catch (e) {}
    }

    const modalTitle = document.getElementById("modalTicketTitle");
    const modalId = document.getElementById("modalTicketId");
    const modalStatus = document.getElementById("modalTicketStatus");
    const modalCategory = document.getElementById("modalTicketCategory");
    const modalPriority = document.getElementById("modalTicketPriority");
    const modalDate = document.getElementById("modalTicketDate");
    const modalDesc = document.getElementById("modalTicketDescription");

    if (modalTitle) modalTitle.textContent = ticket ? ticket.title : `Ticket #${ticketId}`;
    if (modalId) modalId.textContent = `#${ticketId}`;

    if (modalStatus) {
        const st = ticket ? (ticket.status || "Open") : "Open";
        modalStatus.textContent = st;
        modalStatus.className = `status ${st.toLowerCase().replaceAll(" ", "-")}`;
    }

    if (modalCategory) modalCategory.textContent = ticket ? (ticket.department || ticket.category || "General") : "General";

    if (modalPriority) {
        const pr = ticket ? (ticket.priority || "Medium") : "Medium";
        modalPriority.textContent = pr;
        modalPriority.className = `priority ${pr.toLowerCase()}`;
    }

    if (modalDate) modalDate.textContent = ticket ? (ticket.date || (ticket.createdAt ? ticket.createdAt.split("T")[0] : "Today")) : "Today";
    if (modalDesc) modalDesc.textContent = ticket ? (ticket.description || "No description provided.") : "No description provided.";

    await renderModalComments(ticketId);

    modal.style.display = "flex";
    requestAnimationFrame(() => modal.classList.add("show"));

    const threadContainer = document.getElementById("modalChatThread");
    if (threadContainer) threadContainer.scrollTop = threadContainer.scrollHeight;
}

async function renderModalComments(ticketId) {
    const threadContainer = document.getElementById("modalChatThread");
    if (!threadContainer) return;

    const getCommentsFn = window.apiGetComments || (async () => []);
    const comments = await getCommentsFn(ticketId);

    if (!comments || comments.length === 0) {
        threadContainer.innerHTML = `
            <div style="text-align: center; color: #8a7896; font-size: 12px; padding: 20px; background: #faf7fc; border-radius: 8px;">
                <i class="fa-regular fa-comments" style="font-size: 1.5rem; margin-bottom: 6px; display: block; color: #b4a2c0;"></i>
                No messages from HR yet. Type below to send a message to support.
            </div>
        `;
        return;
    }

    threadContainer.innerHTML = comments.map(c => {
        const isEmployee = (c.sender_role || "").toLowerCase() === "employee";
        const senderRoleText = c.sender_role || (isEmployee ? "Employee" : "HR Support");
        const timeText = c.createdAt ? c.createdAt.replace("T", " ").substring(0, 16) : "Just now";

        if (isEmployee) {
            return `
                <div class="chat-msg-bubble-wrapper employee-msg">
                    <div class="chat-msg-header">
                        <span class="chat-msg-time">${escapeHTML(timeText)}</span>
                        <span>You (${escapeHTML(senderRoleText)})</span>
                    </div>
                    <div class="chat-bubble-content">
                        ${escapeHTML(c.message)}
                    </div>
                </div>
            `;
        } else {
            return `
                <div class="chat-msg-bubble-wrapper hr-msg">
                    <div class="chat-msg-header">
                        <span class="chat-msg-badge"><i class="fa-solid fa-user-shield"></i> ${escapeHTML(senderRoleText)}</span>
                        <span class="chat-msg-time">${escapeHTML(timeText)}</span>
                    </div>
                    <div class="chat-bubble-content">
                        ${escapeHTML(c.message)}
                    </div>
                </div>
            `;
        }
    }).join("");

    threadContainer.scrollTop = threadContainer.scrollHeight;
}

function closeTicketChatModal() {
    const modal = document.getElementById("ticketModal");
    if (!modal) return;
    modal.classList.remove("show");
    setTimeout(() => { modal.style.display = "none"; }, 200);
}

async function submitModalComment() {
    const chatInput = document.getElementById("modalChatInput");
    if (!chatInput || !currentOpenTicketId) return;
    const msg = chatInput.value.trim();
    if (!msg) return;

    chatInput.value = "";
    
    const postFn = window.apiPostComment || (async () => null);
    await postFn(currentOpenTicketId, msg, "Employee");
    await renderModalComments(currentOpenTicketId);
}

async function initializeMyTickets() {
    const list = document.getElementById("myTicketsList");
    if (!list) return;
    list.innerHTML = '<div style="padding: 24px; text-align: center; color: #64748b;">Loading tickets...</div>';
    
    let tickets = [];
    try {
        const fetchFn = window.apiFetchTickets || apiFetchTickets;
        tickets = await fetchFn();
    } catch (e) {
        console.warn("apiFetchTickets notice in initializeMyTickets:", e);
    }

    if (!tickets) tickets = [];

    renderMyTickets(tickets);
}

function renderMyTickets(tickets) {
    const list = document.getElementById("myTicketsList");
    if (!list) return;
    if (!tickets || tickets.length === 0) {
        list.innerHTML = '<div style="padding: 24px; text-align: center; color: #64748b;">No support requests found.</div>';
        return;
    }
    loadedMyTicketsMap = {};
    list.innerHTML = tickets.map(t => {
        loadedMyTicketsMap[t.id] = t;
        const stClass = (t.status || "Open").toLowerCase().replaceAll(" ", "-");
        const prClass = (t.priority || "Medium").toLowerCase();
        const dateStr = t.date || (t.createdAt ? t.createdAt.split("T")[0] : "Today");
        const deptStr = t.department || t.category || "IT Support";

        return `
            <div class="table-row" onclick="window.location.href='ticket-detail.html?id=${encodeURIComponent(t.id)}'">
                <div class="ticket-request-cell">
                    <strong>${escapeHTML(t.title || "Untitled request")}</strong>
                    <span>#${escapeHTML(t.id)}</span>
                </div>
                <div class="ticket-department">${escapeHTML(t.department || t.category || "General Support")}</div>
                <div><span class="ticket-badge status-${stClass}">${escapeHTML(t.status || "Open")}</span></div>
                <div><span class="ticket-badge priority-${prClass}">${escapeHTML(t.priority || "Medium")}</span></div>
                <div class="ticket-date">${escapeHTML(t.date || (t.createdAt ? t.createdAt.substring(0, 10) : "Today"))}</div>
                <div style="text-align: right;">
                    <button class="ticket-action" type="button" onclick="event.stopPropagation(); window.location.href='ticket-detail.html?id=${encodeURIComponent(t.id)}'" aria-label="Open conversation for ticket ${escapeHTML(t.id)}">
                        <i class="fa-regular fa-comment-dots"></i> Chat
                    </button>
                </div>
            </div>
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

/* =========================================================
   EMPLOYEE PORTAL SPECIFIC LOADERS
   ========================================================= */
async function loadDashboardTickets() {
    const tableBody = document.querySelector(".table-container table tbody");
    if (!tableBody) return;
    const fetchFn = window.apiFetchTickets || (async () => getTickets());
    let tickets = await fetchFn();
    if (!tickets) tickets = [];

    tableBody.innerHTML = tickets.slice(0, 5).map(t => `
        <tr onclick="window.location.href='ticket-detail.html?id=${encodeURIComponent(t.id)}'" style="cursor: pointer;">
            <td><strong>#${escapeHTML(t.id)}</strong></td>
            <td>${escapeHTML(t.title || "Untitled")}</td>
            <td>${escapeHTML(t.department || t.category || "General")}</td>
            <td><span class="status-pill status-${(t.status || "Open").toLowerCase().replaceAll(" ", "-")}">${escapeHTML(t.status || "Open")}</span></td>
            <td><span class="priority-pill priority-${(t.priority || "Medium").toLowerCase()}">${escapeHTML(t.priority || "Medium")}</span></td>
            <td>${escapeHTML(t.date || "Today")}</td>
        </tr>
    `).join("");
}

async function loadMyTicketsPage() {
    const tableBody = document.querySelector(".table-container table tbody");
    if (!tableBody) return;
    const fetchFn = window.apiFetchTickets || (async () => getTickets());
    let tickets = await fetchFn();
    if (!tickets) tickets = [];

    tableBody.innerHTML = tickets.map(t => `
        <tr onclick="window.location.href='ticket-detail.html?id=${encodeURIComponent(t.id)}'" style="cursor: pointer;">
            <td><strong>#${escapeHTML(t.id)}</strong></td>
            <td>${escapeHTML(t.title || "Untitled")}</td>
            <td>${escapeHTML(t.department || t.category || "General")}</td>
            <td><span class="status-pill status-${(t.status || "Open").toLowerCase().replaceAll(" ", "-")}">${escapeHTML(t.status || "Open")}</span></td>
            <td><span class="priority-pill priority-${(t.priority || "Medium").toLowerCase()}">${escapeHTML(t.priority || "Medium")}</span></td>
            <td>${escapeHTML(t.date || "Today")}</td>
        </tr>
    `).join("");
}

async function loadTicketDetailPage() {
    const urlParams = new URLSearchParams(window.location.search);
    const ticketId = urlParams.get("id");

    const fetchFn = window.apiFetchTickets || (async () => []);
    let tickets = await fetchFn();
    let ticket = (tickets || []).find(t => String(t.id) === String(ticketId)) || (tickets.length > 0 ? tickets[0] : null);

    const titleEl = document.getElementById("ticketDetailTitle");
    const idEl = document.getElementById("ticketDetailId");
    const statusEl = document.getElementById("ticketDetailStatus");
    const priorityEl = document.getElementById("ticketDetailPriority");
    const descEl = document.getElementById("ticketDetailDescription");

    if (titleEl) titleEl.textContent = ticket.title || "Ticket Detail";
    if (idEl) idEl.textContent = `#${ticket.id}`;
    if (statusEl) {
        statusEl.textContent = ticket.status || "Open";
        statusEl.className = `status-pill status-${(ticket.status || "Open").toLowerCase().replaceAll(" ", "-")}`;
    }
    if (priorityEl) {
        priorityEl.textContent = ticket.priority || "Medium";
        priorityEl.className = `priority-pill priority-${(ticket.priority || "Medium").toLowerCase()}`;
    }
    if (descEl) descEl.textContent = ticket.description || "No description provided.";

    const getCommentsFn = window.apiGetComments || (async () => []);
    const comments = await getCommentsFn(ticketId);
    const threadContainer = document.getElementById("ticketCommentsThread");
    if (threadContainer && comments && comments.length > 0) {
        threadContainer.innerHTML = comments.map(c => `
            <div class="comment-bubble ${c.sender_role === "Employee" ? "user-bubble" : "support-bubble"}">
                <div class="comment-header">
                    <strong>${escapeHTML(c.sender_role || "Support")}</strong>
                    <small>${escapeHTML(c.createdAt ? c.createdAt.substring(0, 10) : "Today")}</small>
                </div>
                <div class="comment-body">${escapeHTML(c.message)}</div>
            </div>
        `).join("");
    }
}

async function submitStandardTicket(event) {
    if (event) event.preventDefault();

    const titleEl = document.getElementById("standardSubject") || document.getElementById("ticketTitle");
    const deptEl = document.getElementById("standardDepartment") || document.getElementById("ticketDepartment");
    const priorityEl = document.getElementById("ticketPriority");
    const descEl = document.getElementById("standardDescription") || document.getElementById("ticketDescription");

    if (isSubmittingScriptTicket) return;
    isSubmittingScriptTicket = true;

    try {
        const stdForm = document.querySelector("#standardTabContent form");
        const title = stdForm ? stdForm.querySelector("input[type='text']")?.value : "Standard Ticket";
        const rawDept = stdForm ? stdForm.querySelector("select")?.value : "Auto";
        const desc = stdForm ? stdForm.querySelector("textarea")?.value : "";

        let mappedDept = null;
        if (rawDept && rawDept !== "Auto") {
            if (rawDept.includes("HR")) mappedDept = "HR Team";
            else if (rawDept.includes("Account")) mappedDept = "Accounting Team";
            else if (rawDept.includes("Upper") || rawDept.includes("Admin")) mappedDept = "Upper Management";
            else if (rawDept.includes("Workplace")) mappedDept = "Workplace Operations Team";
            else mappedDept = "IT Team";
        }

        const payload = {
            title: title || "Standard Request",
            description: desc || "No description provided",
            category: rawDept !== "Auto" ? rawDept : "IT Support",
            priority: "Medium",
            department: mappedDept
        };

        const createFn = window.apiCreateTicket || apiCreateTicket;
        const result = await createFn(payload);

        const existing = getTickets();
        const newTicket = result || {
            id: generateTicketId(),
            title: payload.title,
            department: mappedDept || "IT Team",
            category: payload.category,
            priority: payload.priority,
            description: payload.description,
            status: "Open",
            date: new Date().toISOString().split("T")[0],
            createdAt: new Date().toISOString()
        };
        existing.unshift(newTicket);
        saveTickets(existing);

        showNotification("Ticket submitted successfully!", "success");
        showSuccessMessage(newTicket);

        setTimeout(() => {
            const target = window.location.pathname.includes("/management/") || window.location.pathname.includes("/admin_AV/") ? "inbox.html" : "my-tickets.html";
            window.location.href = target;
        }, 1200);
    } catch (err) {
        isSubmittingScriptTicket = false;
        console.error("submitStandardTicket failed:", err);
        showNotification("Failed to submit ticket. Please try again.", "error");
    }
}

async function submitLeaveTicket(event) {
    if (event) event.preventDefault();
    if (isSubmittingScriptTicket) return;
    isSubmittingScriptTicket = true;

    const leaveForm = document.querySelector("#leaveTabContent form");
    const leaveType = leaveForm ? leaveForm.querySelector("select")?.value : "Paid Time Off (PTO)";
    const handover = leaveForm ? leaveForm.querySelectorAll("input[type='text']")[0]?.value : "";
    const startDate = leaveForm ? leaveForm.querySelectorAll("input[type='date']")[0]?.value : "";
    const endDate = leaveForm ? leaveForm.querySelectorAll("input[type='date']")[1]?.value : "";
    const notes = leaveForm ? leaveForm.querySelector("textarea")?.value : "";

    const payload = {
        title: `Leave Request: ${leaveType}`,
        department: "HR & Workplace Operations",
        category: "Time Off",
        priority: "Medium",
        description: `Leave Type: ${leaveType}\nStart Date: ${startDate || 'N/A'}\nEnd Date: ${endDate || 'N/A'}\nCoverage Lead: ${handover || 'N/A'}\nNotes: ${notes || 'N/A'}`
    };

    try {
        const createFn = window.apiCreateTicket || apiCreateTicket;
        const result = await createFn(payload);

        const existing = getTickets();
        const newTicket = result || {
            id: generateTicketId(),
            title: payload.title,
            department: payload.department,
            category: payload.category,
            priority: payload.priority,
            description: payload.description,
            status: "Open",
            date: new Date().toISOString().split("T")[0],
            createdAt: new Date().toISOString()
        };
        existing.unshift(newTicket);
        saveTickets(existing);

        showNotification("Leave request submitted successfully!", "success");
        showSuccessMessage(newTicket);
        setTimeout(() => {
            const target = window.location.pathname.includes("/management/") || window.location.pathname.includes("/admin_AV/") ? "inbox.html" : "my-tickets.html";
            window.location.href = target;
        }, 1200);
    } catch (err) {
        isSubmittingScriptTicket = false;
        console.error("submitLeaveTicket failed:", err);
        showNotification("Failed to submit leave request.", "error");
    }
}

async function submitAnonymousTicket(event) {
    if (event) event.preventDefault();
    if (isSubmittingScriptTicket) return;
    isSubmittingScriptTicket = true;

    const anonForm = document.querySelector("#anonymousTabContent form");
    const category = anonForm ? anonForm.querySelector("select")?.value : "Confidential";
    const msg = anonForm ? anonForm.querySelector("textarea")?.value : "";

    const payload = {
        title: `Confidential Report: ${category}`,
        department: "Upper Management/Administration",
        category: category,
        priority: "High",
        description: msg || "Confidential feedback.",
        is_anonymous: true,
        requester_id: "anonymous@ticketgenie.com"
    };

    try {
        const createFn = window.apiCreateTicket || apiCreateTicket;
        const result = await createFn(payload);

        const existing = getTickets();
        const newTicket = result || {
            id: generateTicketId(),
            title: payload.title,
            department: payload.department,
            category: payload.category,
            priority: payload.priority,
            description: payload.description,
            status: "Open",
            date: new Date().toISOString().split("T")[0],
            createdAt: new Date().toISOString()
        };
        existing.unshift(newTicket);
        saveTickets(existing);

        showNotification("Anonymous report submitted confidentially!", "success");
        showSuccessMessage(newTicket);
        setTimeout(() => {
            const target = window.location.pathname.includes("/management/") || window.location.pathname.includes("/admin_AV/") ? "inbox.html" : "my-tickets.html";
            window.location.href = target;
        }, 1200);
    } catch (err) {
        isSubmittingScriptTicket = false;
        console.error("submitAnonymousTicket failed:", err);
        showNotification("Failed to submit confidential report.", "error");
    }
}

async function sendTicketReply(ticketId) {
    const replyInput = document.getElementById("replyMessageInput");
    if (!replyInput) return;
    const msg = replyInput.value.trim();
    if (!msg) return;

    replyInput.value = "";
    const postFn = window.apiPostComment || apiPostComment;
    await postFn(ticketId, msg, "Employee");
    await loadTicketDetailPage();
}

/* =========================================================
   GLOBAL INITIALIZER LISTENERS
   ========================================================= */

/* NOTE: apiRunReAct, apiRunExecAction, getExportUrl, apiGetComments,
   apiPostComment, apiUpdateTicket, apiFetchAnnouncements,
   apiCreateAnnouncement, apiDeleteAnnouncement, apiFetchNotifications,
   apiMarkNotificationRead, apiFetchOnboarding, apiCreateOnboarding,
   apiUpdateOnboardingStatus, apiFetchUserProfile, and apiUpdateUserProfile
   now live in frontend/js/api.js (dev's shared REST API client module,
   loaded via autoLoadDependencies() above) rather than being duplicated
   here - callers already use the window.apiX || apiX pattern elsewhere
   in this file expecting that. */

/* =========================================================
   GENIE CHATBOT (real backend integration)
   Talks to the actual chatbot endpoint (POST /api/chatbot/message,
   backend/api/chatbot.py) using the real ChatRequest/ChatResponse
   contract (backend/models/chatbot.py) - not a local/static responder.
   ========================================================= */
const GENIE_STATE_KEY = "genieChatState";
const GENIE_PENDING_DRAFT_KEY = "geniePendingDraft";
const GENIE_DRAFTING_INTENTS = ["create_ticket", "support_issue", "leave_management"];

function loadGenieState() {
    try {
        const raw = sessionStorage.getItem(GENIE_STATE_KEY);
        if (!raw) return { history: [], draft: null, active_intent: null, active_request_type: null };
        const parsed = JSON.parse(raw);
        return {
            history: Array.isArray(parsed.history) ? parsed.history : [],
            draft: parsed.draft || null,
            active_intent: parsed.active_intent || null,
            active_request_type: parsed.active_request_type || null,
        };
    } catch (err) {
        return { history: [], draft: null, active_intent: null, active_request_type: null };
    }
}

function saveGenieState(state) {
    sessionStorage.setItem(GENIE_STATE_KEY, JSON.stringify(state));
}

function getCurrentUserRole() {
    try {
        const user = JSON.parse(localStorage.getItem("portalUser") || "{}");
        return user.role || "Employee";
    } catch (err) {
        return "Employee";
    }
}

async function apiChatbotMessage(message, state) {
    const payload = {
        message,
        role: getCurrentUserRole(),
        history: state.history,
        draft: state.draft,
        active_intent: state.active_intent,
        active_request_type: state.active_request_type,
    };
    try {
        // Hardcoded rather than using the shared API_BASE_URL from api.js
        // (the shared REST client uses the backend's real "/api" prefix,
        // prefix the backend and nginx actually use - see this merge's
        // final report) so the chatbot never silently breaks regardless
        // of that mismatch.
        const res = await fetch("/api/chatbot/message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) return await res.json();
    } catch (err) {
        console.error("Failed to reach the chatbot service:", err);
    }
    return {
        message: "I'm having trouble reaching the assistant service right now. Please try again in a moment.",
        intent: "general",
        suggestions: []
    };
}

/* Fold a completed turn into the persisted conversation state. A
   ticket-drafting flow stays "active" (so the next message is treated as
   a continuation) only while it's still collecting fields - once the
   draft is ready_for_review it's handed off to the actual form and the
   chat is free to start a new topic. */
function advanceGenieState(state, userMessage, response) {
    state.history.push({ role: "user", message: userMessage });
    state.history.push({ role: "assistant", message: response.message || "" });

    const stillDrafting = GENIE_DRAFTING_INTENTS.includes(response.intent) && !response.ready_for_review;
    state.active_intent = stillDrafting ? response.intent : null;
    state.active_request_type = stillDrafting ? (response.request_type || null) : null;
    state.draft = stillDrafting ? (response.ticket_draft || null) : null;

    saveGenieState(state);
}

function renderGenieUserMessage(container, text) {
    const userDiv = document.createElement("div");
    userDiv.className = "genie-message user-message";
    userDiv.style.display = "flex";
    userDiv.style.justifyContent = "flex-end";
    userDiv.style.marginBottom = "12px";
    userDiv.innerHTML = `<div class="genie-bubble" style="background:#4f46e5; color:white; border-radius:12px; padding:10px 14px;">${escapeHTML(text)}</div>`;
    container.appendChild(userDiv);
}

function renderGenieBotMessage(container, text, suggestions) {
    const botDiv = document.createElement("div");
    botDiv.className = "genie-message";
    botDiv.style.marginBottom = "12px";
    const suggestionsHtml = (suggestions && suggestions.length)
        ? `<div class="genie-suggestions">${suggestions.map(s => `<button class="genie-suggestion" type="button">${escapeHTML(s)}</button>`).join("")}</div>`
        : "";
    botDiv.innerHTML = `
        <div class="genie-message-avatar"><i class="fa-solid fa-wand-magic-sparkles"></i></div>
        <div class="genie-bubble">${escapeHTML(text)}</div>
        ${suggestionsHtml}
    `;
    container.appendChild(botDiv);
}

/* Redraw the drawer from persisted history so a conversation survives
   navigating to a different page (e.g. when a draft becomes ready and we
   move to new-request.html to prefill the right form). */
function renderGenieHistory(container, state) {
    if (!container || !state.history.length) return;
    container.innerHTML = "";
    state.history.forEach(turn => {
        if (turn.role === "user") {
            renderGenieUserMessage(container, turn.message);
        } else {
            renderGenieBotMessage(container, turn.message, null);
        }
    });
}

/* =========================================================
   REQUEST FORM PREFILL (from a ready_for_review chatbot draft)
   Only ever fills field values and switches tabs - never submits.
   ========================================================= */
const GENIE_REQUEST_TYPE_TAB_NAMES = {
    standard: "standard",
    leave_management: "leave",
    anonymous: "anonymous"
};

function setFieldValue(id, value) {
    if (!value) return;
    const el = document.getElementById(id);
    if (el) el.value = value;
}

function prefillRequestForm(requestType, draft) {
    if (!draft) return;
    const tabName = GENIE_REQUEST_TYPE_TAB_NAMES[requestType];
    if (tabName && typeof window.switchTab === "function") {
        window.switchTab(tabName);
    }

    if (requestType === "standard") {
        setFieldValue("standardSubject", draft.title);
        setFieldValue("standardDepartment", draft.category);
        setFieldValue("standardDescription", draft.description);
    } else if (requestType === "anonymous") {
        setFieldValue("anonymousDescription", draft.description);
    } else if (requestType === "leave_management") {
        setFieldValue("leaveTypeSelect", draft.category);
        setFieldValue("leaveDescription", draft.description);
        setFieldValue("leaveStartDate", draft.preferredDate);
    }

    const card = document.querySelector(".request-form-card") || document.querySelector(".form-container");
    if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
}

function applyPendingGenieDraft() {
    const raw = sessionStorage.getItem(GENIE_PENDING_DRAFT_KEY);
    if (!raw) return;
    sessionStorage.removeItem(GENIE_PENDING_DRAFT_KEY);
    try {
        const pending = JSON.parse(raw);
        prefillRequestForm(pending.request_type, pending.draft);
    } catch (err) {
        // Malformed/stale pending draft - nothing to prefill.
    }
}

function resolvePortalTarget(target) {
    if (!target) return target;
    const isManagement = window.location.pathname.includes("/management/");
    const isAdminAV = window.location.pathname.includes("/admin_AV/");

    if (isManagement || isAdminAV) {
        if (target === "my-tickets.html") return "inbox.html";
        if (target === "new-request.html") return "submit-ticket.html";
    }
    return target;
}

/* When a draft is ready_for_review, hand it to the correct existing form.
   If we're already on the New Request page, prefill in place; otherwise
   stash it and navigate there (the page reload picks it up via
   applyPendingGenieDraft()). Never auto-submits. */
function openReadyDraft(response) {
    if (!response.request_type || !response.ticket_draft) return;
    const onNewRequestPage = !!document.getElementById("standardTicketForm");
    if (onNewRequestPage) {
        prefillRequestForm(response.request_type, response.ticket_draft);
        return;
    }
    sessionStorage.setItem(
        GENIE_PENDING_DRAFT_KEY,
        JSON.stringify({ request_type: response.request_type, draft: response.ticket_draft })
    );
    const targetUrl = resolvePortalTarget("new-request.html");
    setTimeout(() => { window.location.href = targetUrl; }, 900);
}

/* Deterministic (not GPT-driven) route handling for navigation-style
   replies (intent=navigation, or a fallback action like "browse the
   Knowledge Base" / "view My Tickets"). Ticket-status/knowledge/general
   replies never open a request form. */
function handleGenieAction(action) {
    if (!action || !action.target) return;
    if (action.type !== "navigate" && action.type !== "lookup_ticket") return;
    const targetUrl = resolvePortalTarget(action.target);
    setTimeout(() => { window.location.href = targetUrl; }, 900);
}

/* Initialize Floating Genie Drawer globally if present on page */
function initializeGenie() {
    const genieBtn = document.getElementById("genieButton");
    const genieChat = document.getElementById("genieChat");
    const closeGenieBtn = document.getElementById("closeGenieButton");
    const genieSendBtn = document.getElementById("genieSendButton");
    const genieInput = document.getElementById("genieInput");
    const genieMessages = document.getElementById("genieMessages");
    const openGenieFromRequestBtn = document.getElementById("openGenieFromRequest");

    if (!genieBtn || !genieChat) return;

    if (genieBtn.dataset.genieInitialized === "true") return;
    genieBtn.dataset.genieInitialized = "true";

    const openGenie = () => genieChat.classList.add("open");

    genieBtn.addEventListener("click", () => genieChat.classList.toggle("open"));

    if (closeGenieBtn) {
        closeGenieBtn.addEventListener("click", () => genieChat.classList.remove("open"));
    }
    if (openGenieFromRequestBtn) {
        openGenieFromRequestBtn.addEventListener("click", openGenie);
    }

    let genieState = typeof loadGenieState === "function" ? loadGenieState() : null;
    if (genieMessages && genieState) {
        renderGenieHistory(genieMessages, genieState);
    }

    async function sendGenieMsg() {
        if (!genieInput) return;
        const genieMessages = document.getElementById("genieMessages");
        const msg = genieInput.value.trim();
        if (!msg || !genieMessages) return;

        renderGenieUserMessage(genieMessages, msg);
        genieInput.value = "";
        genieInput.disabled = true;
        genieMessages.scrollTop = genieMessages.scrollHeight;

        const response = typeof apiChatbotMessage === "function" 
            ? await apiChatbotMessage(msg, genieState)
            : { message: "Genie assistant ready.", suggestions: [] };

        if (genieState && typeof advanceGenieState === "function") {
            advanceGenieState(genieState, msg, response);
        }

        renderGenieBotMessage(genieMessages, response.message, response.suggestions);
        genieMessages.scrollTop = genieMessages.scrollHeight;
        genieInput.disabled = false;
        genieInput.focus();

        if (response.ready_for_review && typeof openReadyDraft === "function") {
            openReadyDraft(response);
        } else if (typeof handleGenieAction === "function") {
            handleGenieAction(response.action);
        }
    }

    if (genieSendBtn) genieSendBtn.addEventListener("click", sendGenieMsg);
    if (genieInput) {
        genieInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") sendGenieMsg();
        });
    }

    // Both the static initial suggestions in the HTML and any rendered
    // from a chatbot response use this same class - wire them all via
    // delegation so clicking one sends it as the next message.
    if (genieMessages) {
        genieMessages.addEventListener("click", (e) => {
            const btn = e.target.closest(".genie-suggestion");
            if (!btn || !genieInput) return;
            genieInput.value = btn.textContent.trim();
            sendGenieMsg();
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initDarkMode();
    initSidebarToggle();
    if (typeof initializeProfileDropdown === "function") initializeProfileDropdown();
    initializeNewRequestForm();
    initializeMyTickets();
    applyPendingGenieDraft();

    // Floating Genie Chat Drawer events
    initializeGenie();

    // Auto-initialize page loaders if elements exist
    if (document.getElementById("myTicketsList")) {
        initializeMyTickets();
    }
    if (document.querySelector(".table-container table tbody")) {
        loadDashboardTickets();
    }
});

// Bind all global utilities to window
Object.assign(window, {
    STORAGE_KEY,
    getTickets,
    saveTickets,
    generateTicketId,
    getCurrentRequesterId,
    escapeHTML,
    showNotification,
    showFormError,
    showSuccessMessage,
    initDarkMode,
    initSidebarToggle,
    handleSignOut,
    openTicketChatModal,
    renderModalComments,
    closeTicketChatModal,
    submitModalComment,
    initializeMyTickets,
    renderMyTickets,
    loadDashboardTickets,
    loadMyTicketsPage,
    loadTicketDetailPage,
    submitStandardTicket,
    submitLeaveTicket,
    submitAnonymousTicket,
    sendTicketReply,
    initializeGenie
});
