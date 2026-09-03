/* =========================================================
   TICKETGENIE EMPLOYEE PORTAL MODULE
   Dedicated handlers for Employee Requests, Tickets Grid, and Threads
   ========================================================= */

var STORAGE_KEY = window.STORAGE_KEY || "ticketGenieTickets";
var loadedMyTicketsMap = window.loadedMyTicketsMap || {};

function getTickets() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem("employee_tickets");
        if (stored) return JSON.parse(stored);
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

function mapDepartmentName(val) {
    if (!val || val === "Auto") return null;
    const lower = val.toLowerCase();
    if (lower.includes("hr") || lower.includes("workplace") || lower.includes("benefit")) return "HR Team";
    if (/\bit\b/.test(lower) || lower.includes("hardware") || lower.includes("software") || lower.includes("vpn") || lower.includes("tech")) return "IT Team";
    if (lower.includes("account")) return "Accounting Team";
    if (lower.includes("upper") || lower.includes("admin")) return "Upper Management";
    return "IT Team";
}

async function loadDashboardTickets() {
    const recentContainer = document.getElementById("recentTicketsContainer");
    const tableBody = document.querySelector(".table-container table tbody");
    if (!recentContainer && !tableBody) return;

    let tickets = [];
    try {
        const fetchFn = window.apiFetchTickets || apiFetchTickets;
        tickets = await fetchFn();
    } catch (e) {
        console.warn("apiFetchTickets notice in loadDashboardTickets:", e);
    }
    if (!tickets) tickets = [];

    // Calculate metrics
    let openCount = 0;
    let inProgressCount = 0;
    let resolvedCount = 0;

    tickets.forEach(t => {
        const status = (t.status || "").toLowerCase();
        if (status.includes("in_progress") || status.includes("in progress")) {
            inProgressCount++;
        } else if (status.includes("resolved") || status.includes("closed")) {
            resolvedCount++;
        } else {
            openCount++;
        }
    });

    const elemOpen = document.getElementById("countOpen");
    const elemInProgress = document.getElementById("countInProgress");
    const elemResolved = document.getElementById("countResolved");
    if (elemOpen) elemOpen.textContent = openCount;
    if (elemInProgress) elemInProgress.textContent = inProgressCount;
    if (elemResolved) elemResolved.textContent = resolvedCount;

    if (recentContainer) {
        if (tickets.length === 0) {
            recentContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: #64748b;">No recent support requests found.</div>';
            return;
        }
        recentContainer.innerHTML = tickets.slice(0, 5).map(t => `
            <div onclick="window.location.href='ticket-detail.html?id=${encodeURIComponent(t.id)}'" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='#f8fafc'">
                <div style="display: flex; align-items: center; gap: 16px;">
                    <span style="font-weight: 700; color: #6f4b82; font-size: 13px;">#${escapeHTML(t.id)}</span>
                    <div>
                        <strong style="display: block; font-size: 14px; color: #1e293b; margin-bottom: 2px;">${escapeHTML(t.title || "Untitled")}</strong>
                        <span style="font-size: 12px; color: #64748b;">${escapeHTML(t.department || t.category || "General")} • Submitted ${escapeHTML(t.date || "Today")}</span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span class="badge badge-${(t.status || "Open").toLowerCase().replaceAll(" ", "-")}">${escapeHTML(t.status || "Open")}</span>
                    <i class="fa-solid fa-chevron-right" style="font-size: 12px; color: #94a3b8;"></i>
                </div>
            </div>
        `).join("");
    }

    if (tableBody) {
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
            <div class="tickets-table-row" style="display: grid; grid-template-columns: 2.2fr 1.6fr 1fr 1fr 1fr 110px; gap: 16px; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e1e6e2; font-size: 13px; transition: background 0.15s; cursor: pointer;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'" onclick="window.location.href='ticket-detail.html?id=${encodeURIComponent(t.id)}'">
                <div>
                    <strong style="color: #1e293b; font-size: 14px;">${escapeHTML(t.title || "Untitled")}</strong>
                    <div style="font-size: 12px; color: #64748b; margin-top: 2px;">#${escapeHTML(t.id)}</div>
                </div>
                <div><span style="font-weight: 500; color: #334155;">${escapeHTML(deptStr)}</span></div>
                <div><span class="badge priority-${prClass}" style="padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">${escapeHTML(t.priority || "Medium")}</span></div>
                <div><span class="badge status-${stClass}" style="padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">${escapeHTML(t.status || "Open")}</span></div>
                <div style="color: #64748b;">${escapeHTML(dateStr)}</div>
                <div style="text-align: right;">
                    <button type="button" style="background: #eef2ff; color: #4f46e5; border: 1px solid #c7d2fe; border-radius: 6px; padding: 6px 12px; font-size: 12px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;" onclick="event.stopPropagation(); window.location.href='ticket-detail.html?id=${encodeURIComponent(t.id)}'">
                        <i class="fa-regular fa-comments"></i> Chat
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

async function loadTicketDetailPage() {
    const urlParams = new URLSearchParams(window.location.search);
    const ticketId = urlParams.get("id");
    const container = document.getElementById("ticketDetailContainer");
    if (!container) return;

    if (!ticketId) {
        container.innerHTML = renderTicketDetailError("No ticket was selected.");
        return;
    }

    let ticket;
    try {
        const fetchFn = window.apiFetchTicket;
        if (typeof fetchFn !== "function") throw new Error("Ticket API is unavailable.");
        ticket = await fetchFn(ticketId);
    } catch (err) {
        console.error("loadTicketDetailPage failed:", err);
        container.innerHTML = renderTicketDetailError(
            err && err.message ? err.message : "Unable to load this ticket."
        );
        return;
    }

    container.innerHTML = `
        <div style="background: white; border-radius: 12px; padding: 28px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h1 style="font-size: 22px; font-weight: 700; color: #0f172a; margin-bottom: 6px;">${escapeHTML(ticket.title)}</h1>
                    <span style="font-size: 13px; color: #64748b;">Ticket ID: <strong>#${escapeHTML(ticket.id)}</strong></span>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button type="button" onclick="downloadTicketDocument('${escapeHTML(ticket.id)}', 'pdf', this)" style="padding: 8px 14px; background: #ef4444; color: white; border: 0; border-radius: 6px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;"><i class="fa-solid fa-file-pdf"></i> Export PDF</button>
                    <button type="button" onclick="downloadTicketDocument('${escapeHTML(ticket.id)}', 'docx', this)" style="padding: 8px 14px; background: #2563eb; color: white; border: 0; border-radius: 6px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;"><i class="fa-solid fa-file-word"></i> Export DOCX</button>
                </div>
            </div>

            <div style="display: flex; gap: 16px; font-size: 13px; color: #475569; margin-bottom: 20px; flex-wrap: wrap; background: #f8fafc; padding: 12px 16px; border-radius: 8px;">
                <div><strong>Category:</strong> ${escapeHTML(ticket.category || ticket.department || "IT Support")}</div>
                <div><strong>Priority:</strong> <span class="badge priority-${(ticket.priority||'Medium').toLowerCase()}">${escapeHTML(ticket.priority || "Medium")}</span></div>
                <div><strong>Status:</strong> <span class="badge status-${(ticket.status||'Open').toLowerCase().replaceAll(' ','-')}">${escapeHTML(ticket.status || "Open")}</span></div>
                <div><strong>Date:</strong> ${escapeHTML(ticket.date || "Today")}</div>
            </div>

            <div style="font-size: 14px; color: #334155; line-height: 1.6; border-top: 1px solid #f1f5f9; padding-top: 16px;">
                <strong>Issue Description:</strong>
                <p style="margin-top: 6px;">${escapeHTML(ticket.description || "No description provided.")}</p>
            </div>
        </div>

        <!-- Threaded Chat Section -->
        <div style="background: white; border-radius: 12px; padding: 28px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <h2 style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 20px; display: flex; align-items: center; gap: 8px;"><i class="fa-regular fa-comments"></i> Support Conversation Thread</h2>
            <div id="ticketCommentsThread" style="display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px; max-height: 400px; overflow-y: auto; padding-right: 8px;">
                <div style="text-align: center; color: #94a3b8; font-size: 13px;">Loading conversation...</div>
            </div>

            <div style="display: flex; gap: 12px;">
                <input type="text" id="replyMessageInput" placeholder="Type a message or response to support..." style="flex: 1; padding: 12px 16px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px;">
                <button type="button" onclick="sendTicketReply('${escapeHTML(ticket.id)}')" style="background: #4f46e5; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;"><i class="fa-solid fa-paper-plane"></i> Send</button>
            </div>
        </div>
    `;

    await renderTicketCommentsThread(ticketId);

    const replyInput = document.getElementById("replyMessageInput");
    if (replyInput) {
        replyInput.addEventListener("keydown", event => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendTicketReply(ticketId);
            }
        });
    }
}

function renderTicketDetailError(message) {
    return `
        <div role="alert" style="padding: 32px; text-align: center; color: #991b1b; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 12px;">
            <i class="fa-solid fa-circle-exclamation" style="font-size: 24px; margin-bottom: 10px;"></i>
            <div style="font-weight: 700; margin-bottom: 6px;">Conversation unavailable</div>
            <div style="font-size: 13px;">${escapeHTML(message)}</div>
            <a href="my-tickets.html" style="display: inline-block; margin-top: 16px; color: #6f4b82; font-weight: 700;">Return to My Requests</a>
        </div>
    `;
}

async function downloadTicketDocument(ticketId, format, button) {
    const originalHtml = button ? button.innerHTML : "";
    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';
    }
    try {
        if (typeof window.apiDownloadTicketDocument !== "function") {
            throw new Error("Document export service is unavailable.");
        }
        await window.apiDownloadTicketDocument(ticketId, format);
        showNotification(`${format.toUpperCase()} downloaded.`, "success");
    } catch (err) {
        console.error("downloadTicketDocument failed:", err);
        showNotification(err.message || "Unable to generate the document.", "error");
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = originalHtml;
        }
    }
}

async function renderTicketCommentsThread(ticketId) {
    const threadContainer = document.getElementById("ticketCommentsThread");
    if (!threadContainer) return;
    let comments;
    try {
        const getCommentsFn = window.apiGetComments;
        if (typeof getCommentsFn !== "function") throw new Error("Conversation API is unavailable.");
        comments = await getCommentsFn(ticketId);
    } catch (err) {
        console.error("renderTicketCommentsThread failed:", err);
        threadContainer.innerHTML = `<div role="alert" style="text-align:center;color:#991b1b;padding:20px;background:#fff1f2;border-radius:8px;">${escapeHTML(err.message || "Unable to load the conversation.")}</div>`;
        return;
    }

    if (!comments || comments.length === 0) {
        threadContainer.innerHTML = `
            <div style="text-align: center; color: #64748b; font-size: 13px; padding: 24px; background: #f8fafc; border-radius: 8px;">
                No messages from support yet. Use the field below to send an update.
            </div>
        `;
        return;
    }

    const user = JSON.parse(localStorage.getItem("portalUser") || '{}');
    const currentName = user.name || "Employee";

    threadContainer.innerHTML = comments.map(c => {
        const isEmp = (c.sender_role === 'Employee' || c.sender_role === 'User' || c.sender_id === user.objectId);
        const displayName = c.sender_name || (isEmp ? currentName : (c.sender_role || "Support Agent"));
        const displayLabel = `${escapeHTML(displayName)} (${escapeHTML(c.sender_role || 'Support')})`;
        const badgeColor = isEmp ? '#16a34a' : '#4f46e5';
        const bgColor = isEmp ? '#f0fdf4' : '#eef2ff';

        return `
            <div style="background: ${bgColor}; border-left: 4px solid ${badgeColor}; padding: 14px 18px; border-radius: 8px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; font-size: 12px; color: #64748b; margin-bottom: 6px;">
                    <strong style="color: ${badgeColor};">${displayLabel}</strong>
                    <span>${escapeHTML(c.createdAt ? c.createdAt.substring(0, 16).replace("T", " ") : "Today")}</span>
                </div>
                <div style="font-size: 14px; color: #1e293b; line-height: 1.5;">${escapeHTML(c.message)}</div>
            </div>
        `;
    }).join("");

    threadContainer.scrollTop = threadContainer.scrollHeight;
}

let isSubmittingEmployeeTicket = false;

async function submitStandardTicket(event) {
    if (event) event.preventDefault();
    if (isSubmittingEmployeeTicket) return;
    isSubmittingEmployeeTicket = true;

    const titleEl = document.getElementById("standardSubject") || document.getElementById("ticketTitle");
    const deptEl = document.getElementById("standardDepartment") || document.getElementById("ticketDepartment");
    const priorityEl = document.getElementById("ticketPriority");
    const descEl = document.getElementById("standardDescription") || document.getElementById("ticketDescription");

    const titleStr = titleEl ? titleEl.value.trim() : "";
    let descStr = descEl ? descEl.value.trim() : "";

    if (!titleStr) {
        isSubmittingEmployeeTicket = false;
        showNotification("Please enter a title for your support request.", "error");
        return;
    }

    if (descStr.length < 10) {
        descStr = (descStr + " (Detailed support request submitted via employee portal)").trim();
    }

    const rawDept = deptEl ? deptEl.value : "Auto";
    const mappedDept = mapDepartmentName(rawDept);

    const payload = {
        title: titleStr.length < 3 ? titleStr + " (Ticket)" : titleStr,
        description: descStr,
        category: rawDept !== "Auto" ? rawDept : "IT Support",
        priority: priorityEl ? priorityEl.value : "Medium",
        department: mappedDept
    };

    try {
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
        if (typeof showSuccessMessage === 'function') showSuccessMessage(newTicket);

        setTimeout(() => { window.location.href = "my-tickets.html"; }, 1200);
    } catch (err) {
        isSubmittingEmployeeTicket = false;
        console.error("submitStandardTicket failed:", err);
        showNotification("Failed to submit ticket. Please check your connection.", "error");
    }
}

async function submitLeaveTicket(event) {
    if (event) event.preventDefault();
    if (isSubmittingEmployeeTicket) return;
    isSubmittingEmployeeTicket = true;

    const leaveForm = document.querySelector("#leaveTabContent form");
    const leaveType = leaveForm ? leaveForm.querySelector("select")?.value : "Paid Time Off (PTO)";
    const handover = leaveForm ? leaveForm.querySelectorAll("input[type='text']")[0]?.value : "";
    const startDate = leaveForm ? leaveForm.querySelectorAll("input[type='date']")[0]?.value : "";
    const endDate = leaveForm ? leaveForm.querySelectorAll("input[type='date']")[1]?.value : "";
    const notes = leaveForm ? leaveForm.querySelector("textarea")?.value : "";

    const payload = {
        title: `Leave Request: ${leaveType}`,
        department: "HR Team",
        category: "Time Off",
        priority: "Medium",
        description: `Leave Type: ${leaveType}\nStart Date: ${startDate || 'N/A'}\nEnd Date: ${endDate || 'N/A'}\nCoverage Lead: ${handover || 'N/A'}\nNotes: ${notes || 'Detailed PTO submission'}`
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
        if (typeof showSuccessMessage === 'function') showSuccessMessage(newTicket);
        setTimeout(() => { window.location.href = "my-tickets.html"; }, 1200);
    } catch (err) {
        isSubmittingEmployeeTicket = false;
        console.error("submitLeaveTicket failed:", err);
        showNotification("Failed to submit leave request.", "error");
    }
}

async function submitAnonymousTicket(event) {
    if (event) event.preventDefault();
    if (isSubmittingEmployeeTicket) return;
    isSubmittingEmployeeTicket = true;

    const anonForm = document.querySelector("#anonymousTabContent form");
    const category = anonForm ? anonForm.querySelector("select")?.value : "Confidential";
    const msg = anonForm ? anonForm.querySelector("textarea")?.value : "";

    const payload = {
        title: `Confidential Report: ${category}`,
        department: "Upper Management",
        category: category,
        priority: "High",
        description: (msg && msg.length >= 10) ? msg : (msg + " (Confidential anonymous workplace submission)").trim(),
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
        if (typeof showSuccessMessage === 'function') showSuccessMessage(newTicket);
        setTimeout(() => { window.location.href = "my-tickets.html"; }, 1200);
    } catch (err) {
        isSubmittingEmployeeTicket = false;
        console.error("submitAnonymousTicket failed:", err);
        showNotification("Failed to submit confidential report.", "error");
    }
}

async function sendTicketReply(ticketId) {
    const replyInput = document.getElementById("replyMessageInput");
    if (!replyInput) return;
    const msg = replyInput.value.trim();
    if (!msg) return;

    const sendButton = replyInput.parentElement?.querySelector("button");
    replyInput.disabled = true;
    if (sendButton) sendButton.disabled = true;
    try {
        const postFn = window.apiPostComment;
        if (typeof postFn !== "function") throw new Error("Conversation API is unavailable.");
        await postFn(ticketId, msg, "Employee");
        replyInput.value = "";
        await renderTicketCommentsThread(ticketId);
        showNotification("Message sent.", "success");
    } catch (err) {
        console.error("sendTicketReply failed:", err);
        showNotification(err.message || "Unable to send your message.", "error");
    } finally {
        replyInput.disabled = false;
        if (sendButton) sendButton.disabled = false;
        replyInput.focus();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("myTicketsList")) {
        initializeMyTickets();
    }
    if (document.getElementById("recentTicketsContainer") || document.querySelector(".table-container table tbody")) {
        loadDashboardTickets();
    }
    if (document.getElementById("ticketDetailContainer")) {
        loadTicketDetailPage();
    }
});

Object.assign(window, {
    STORAGE_KEY,
    getTickets,
    saveTickets,
    generateTicketId,
    getCurrentRequesterId,
    loadDashboardTickets,
    initializeMyTickets,
    renderMyTickets,
    loadTicketDetailPage,
    downloadTicketDocument,
    submitStandardTicket,
    submitLeaveTicket,
    submitAnonymousTicket,
    sendTicketReply
});
