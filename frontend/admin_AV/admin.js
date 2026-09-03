/* =========================================================
   TICKETGENIE OPERATIONS & ADMIN PORTAL MODULE
   Dedicated handlers for Manager, Ticketer, and Admin queues
   ========================================================= */

async function loadAdminDashboard() {
    const tableBody = document.querySelector(".table-container table tbody");
    if (!tableBody) return;
    try {
        const fetchFn = window.apiFetchTickets || (async () => []);
        const tickets = await fetchFn({ adminView: true });
        if (tickets && tickets.length > 0) {
            tableBody.innerHTML = tickets.map(t => `
                <tr>
                    <td><strong>#${escapeHTML(t.id)}</strong></td>
                    <td>${escapeHTML(t.title || 'Untitled')}</td>
                    <td>${escapeHTML(t.department || t.category || 'General')}</td>
                    <td><span class="badge priority-${(t.priority||'Medium').toLowerCase()}">${escapeHTML(t.priority || 'Medium')}</span></td>
                    <td><span class="badge status-${(t.status||'Open').toLowerCase().replaceAll(' ','-')}">${escapeHTML(t.status || 'Open')}</span></td>
                    <td>${escapeHTML(t.date || 'Today')}</td>
                </tr>
            `).join("");
        }
    } catch (e) {
        console.warn("loadAdminDashboard error:", e);
    }
}

async function loadAnnouncements() {
    const listEl = document.getElementById("announcementsList");
    if (!listEl) return;
    try {
        const fetchFn = window.apiFetchAnnouncements || (async () => []);
        const announcements = await fetchFn();
        if (announcements && announcements.length > 0) {
            listEl.innerHTML = announcements.map(a => `
                <div style="padding: 16px; border: 1px solid #cbd5e1; border-radius: 8px; margin-bottom: 12px; background: white;">
                    <h4 style="margin: 0 0 6px 0; font-size: 15px; color: #1e293b;">${escapeHTML(a.title)}</h4>
                    <p style="margin: 0; font-size: 13px; color: #475569;">${escapeHTML(a.content)}</p>
                </div>
            `).join("");
            return;
        }
    } catch (e) {
        console.warn("loadAnnouncements error:", e);
    }
    listEl.innerHTML = `<div style="padding: 16px; color: #64748b;">No company announcements posted.</div>`;
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.querySelector(".table-container table tbody")) {
        loadAdminDashboard();
    }
    if (document.getElementById("announcementsList")) {
        loadAnnouncements();
    }
});

Object.assign(window, {
    loadAdminDashboard,
    loadAnnouncements
});
