/* =========================================================
   TICKETGENIE - PORTAL CALENDAR
   ========================================================= */

const CAL_STORAGE_KEY = "ticketGenieCalendarEvents";
const CAL_EVENT_TYPES = ["pto", "maintenance", "sla", "onboarding", "offboarding"];

const CAL_TYPE_META = {
    pto: { label: "Approved Time Off", pillClass: "pill-pto" },
    maintenance: { label: "Server Maintenance", pillClass: "pill-maintenance" },
    sla: { label: "Ticket / SLA Deadline", pillClass: "pill-sla" },
    onboarding: { label: "Onboarding", pillClass: "pill-onboarding" },
    offboarding: { label: "Offboarding", pillClass: "pill-offboarding" }
};

let calState = {
    date: new Date(),
    view: "month",
    activeFilters: new Set(CAL_EVENT_TYPES),
    events: []
};

function calFormatDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

function calAddDays(date, days) {
    const copy = new Date(date);
    copy.setDate(copy.getDate() + days);
    return copy;
}

/* =========================================================
   EVENT DATA (seeded from tickets + sample IT operations data)
   ========================================================= */
function calBuildDefaultEvents(tickets) {
    const today = new Date();
    const events = [];

    tickets.forEach(ticket => {
        if ((ticket.category || "").toLowerCase() === "time off" && ticket.status !== "Rejected") {
            events.push({
                id: `evt-${ticket.id}`,
                type: "pto",
                title: `PTO: ${ticket.title || "Time Off"}`,
                date: ticket.date || calFormatDate(today),
                ticketId: ticket.id,
                summary: ticket.description || "Approved time off request."
            });
        }
        if ((ticket.priority || "").toLowerCase() === "high" && ticket.status !== "Resolved") {
            events.push({
                id: `evt-sla-${ticket.id}`,
                type: "sla",
                title: `SLA Due: ${ticket.title || ticket.id}`,
                date: ticket.date || calFormatDate(today),
                time: "17:00",
                ticketId: ticket.id,
                summary: `High priority ticket must be resolved before SLA breach.`
            });
        }
    });

    const samples = [
        { offset: -1, type: "maintenance", title: "Server Reboot - Prod Cluster", time: "22:00", summary: "Planned reboot of production application servers. Expect brief downtime." },
        { offset: 2, type: "maintenance", title: "Software Update - VPN Gateway", time: "20:00", summary: "Security patch rollout for the VPN gateway appliances." },
        { offset: 1, type: "onboarding", title: "New Hire Onboarding - J. Alvarez", time: "09:00", summary: "Laptop and account provisioning due before start date." },
        { offset: 4, type: "onboarding", title: "New Hire Onboarding - R. Chen", time: "09:00", summary: "IT to prepare workstation and access badges." },
        { offset: 3, type: "offboarding", title: "Offboarding - M. Patel", time: "17:00", summary: "Revoke system access and collect company equipment." },
        { offset: 6, type: "offboarding", title: "Offboarding - T. Nguyen", time: "17:00", summary: "Final day; disable accounts at end of business." },
        { offset: -3, type: "pto", title: "PTO: S. Williams", summary: "Approved vacation, out of office." },
        { offset: 5, type: "pto", title: "PTO: D. Kim", summary: "Approved vacation, out of office." },
        { offset: -2, type: "sla", title: "SLA Due: Network Outage Report", time: "12:00", summary: "Incident report must be finalized before SLA breach." }
    ];

    samples.forEach((sample, index) => {
        events.push({
            id: `evt-sample-${index}`,
            type: sample.type,
            title: sample.title,
            date: calFormatDate(calAddDays(today, sample.offset)),
            time: sample.time || null,
            ticketId: sample.ticketId || null,
            summary: sample.summary
        });
    });

    return events;
}

async function calLoadEvents() {
    const stored = localStorage.getItem(CAL_STORAGE_KEY);
    if (stored) {
        try { return JSON.parse(stored); } catch (e) { /* fall through to rebuild */ }
    }
    const tickets = await apiFetchTickets();
    const events = calBuildDefaultEvents(tickets);
    localStorage.setItem(CAL_STORAGE_KEY, JSON.stringify(events));
    return events;
}

function calSaveEvents() {
    localStorage.setItem(CAL_STORAGE_KEY, JSON.stringify(calState.events));
}

function calGetVisibleEvents() {
    return calState.events.filter(evt => calState.activeFilters.has(evt.type));
}

function calGetEventsForDate(dateStr) {
    return calGetVisibleEvents().filter(evt => evt.date === dateStr);
}

/* =========================================================
   RENDERING
   ========================================================= */
function calRenderPeriodLabel() {
    const label = document.getElementById("calPeriodLabel");
    if (!label) return;
    const options = { month: "long", year: "numeric" };
    if (calState.view === "month") {
        label.textContent = calState.date.toLocaleDateString("en-US", options);
    } else if (calState.view === "week") {
        const start = calGetWeekStart(calState.date);
        const end = calAddDays(start, 6);
        label.textContent = `${start.toLocaleDateString("en-US", { month: "short", day: "numeric" })} - ${end.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
    } else {
        label.textContent = calState.date.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    }
}

function calGetWeekStart(date) {
    const copy = new Date(date);
    const day = copy.getDay();
    copy.setDate(copy.getDate() - day);
    copy.setHours(0, 0, 0, 0);
    return copy;
}

function calRenderEventPill(evt) {
    const meta = CAL_TYPE_META[evt.type] || { pillClass: "pill-sla" };
    const timePrefix = evt.time ? `${evt.time} ` : "";
    return `<button type="button" class="event-pill ${meta.pillClass}" draggable="true" data-event-id="${evt.id}" title="${escapeHTML(evt.title)}">${escapeHTML(timePrefix + evt.title)}</button>`;
}

function calRenderMonth() {
    const body = document.getElementById("calBody");
    if (!body) return;

    const year = calState.date.getFullYear();
    const month = calState.date.getMonth();
    const firstOfMonth = new Date(year, month, 1);
    const gridStart = calAddDays(firstOfMonth, -firstOfMonth.getDay());
    const todayStr = calFormatDate(new Date());

    const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    let headHtml = '<div class="month-grid-head">';
    dayNames.forEach(d => { headHtml += `<div>${d}</div>`; });
    headHtml += "</div>";

    let gridHtml = '<div class="month-grid">';
    for (let i = 0; i < 42; i++) {
        const cellDate = calAddDays(gridStart, i);
        const cellDateStr = calFormatDate(cellDate);
        const isOtherMonth = cellDate.getMonth() !== month;
        const isToday = cellDateStr === todayStr;
        const dayEvents = calGetEventsForDate(cellDateStr);
        const visibleEvents = dayEvents.slice(0, 3);
        const extraCount = dayEvents.length - visibleEvents.length;

        gridHtml += `<div class="month-cell${isOtherMonth ? " other-month" : ""}${isToday ? " today" : ""}" data-date="${cellDateStr}">`;
        gridHtml += `<span class="cell-date${isToday ? " is-today" : ""}">${cellDate.getDate()}</span>`;
        gridHtml += '<div class="cell-events">';
        visibleEvents.forEach(evt => { gridHtml += calRenderEventPill(evt); });
        gridHtml += "</div>";
        if (extraCount > 0) gridHtml += `<div class="cell-more">+${extraCount} more</div>`;
        gridHtml += "</div>";
    }
    gridHtml += "</div>";

    body.innerHTML = headHtml + gridHtml;
    calAttachDragAndDrop();
    calAttachPillClicks();
}

function calRenderWeek() {
    const body = document.getElementById("calBody");
    if (!body) return;
    const weekStart = calGetWeekStart(calState.date);
    calRenderTimeGrid(body, weekStart, 7);
}

function calRenderDay() {
    const body = document.getElementById("calBody");
    if (!body) return;
    const dayStart = new Date(calState.date);
    dayStart.setHours(0, 0, 0, 0);
    calRenderTimeGrid(body, dayStart, 1);
}

function calRenderTimeGrid(body, startDate, numDays) {
    const todayStr = calFormatDate(new Date());
    const hours = Array.from({ length: 24 }, (_, i) => i);

    let headHtml = '<div class="time-grid-head" style="grid-template-columns: 60px repeat(' + numDays + ', 1fr);">';
    headHtml += '<div></div>';
    const days = [];
    for (let i = 0; i < numDays; i++) {
        const d = calAddDays(startDate, i);
        days.push(d);
        const dStr = calFormatDate(d);
        headHtml += `<div class="time-grid-head-col"><div class="dow">${d.toLocaleDateString("en-US", { weekday: "short" })}</div><div class="dnum" style="${dStr === todayStr ? "color:#4f46e5;" : ""}">${d.getDate()}</div></div>`;
    }
    headHtml += "</div>";

    let bodyHtml = '<div class="time-grid-wrap"><div class="time-grid-body" style="grid-template-columns: 60px repeat(' + numDays + ', 1fr);">';
    bodyHtml += '<div class="time-col-labels">';
    hours.forEach(h => {
        const label = h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`;
        bodyHtml += `<div class="time-label">${label}</div>`;
    });
    bodyHtml += "</div>";

    days.forEach(d => {
        const dStr = calFormatDate(d);
        const dayEvents = calGetEventsForDate(dStr).filter(e => e.time);
        const allDayEvents = calGetEventsForDate(dStr).filter(e => !e.time);
        bodyHtml += `<div class="time-day-col" data-date="${dStr}">`;
        hours.forEach(() => { bodyHtml += '<div class="time-slot"></div>'; });
        allDayEvents.forEach((evt, idx) => {
            const meta = CAL_TYPE_META[evt.type] || { pillClass: "pill-sla" };
            bodyHtml += `<div class="time-event ${meta.pillClass}" data-event-id="${evt.id}" style="top:${idx * 22}px; height:20px;">${escapeHTML(evt.title)}</div>`;
        });
        dayEvents.forEach(evt => {
            const [h, m] = evt.time.split(":").map(Number);
            const top = h * 56 + (m / 60) * 56 + (allDayEvents.length * 22);
            const meta = CAL_TYPE_META[evt.type] || { pillClass: "pill-sla" };
            bodyHtml += `<div class="time-event ${meta.pillClass}" data-event-id="${evt.id}" style="top:${top}px; height:50px;">${escapeHTML(evt.time + " " + evt.title)}</div>`;
        });
        bodyHtml += "</div>";
    });
    bodyHtml += "</div></div>";

    body.innerHTML = headHtml + bodyHtml;
    calAttachPillClicks();
}

function calRender() {
    calRenderPeriodLabel();
    if (calState.view === "month") calRenderMonth();
    else if (calState.view === "week") calRenderWeek();
    else calRenderDay();
}

/* =========================================================
   DRAG & DROP RESCHEDULING (month view)
   ========================================================= */
function calAttachDragAndDrop() {
    const pills = document.querySelectorAll(".event-pill");
    pills.forEach(pill => {
        pill.addEventListener("dragstart", event => {
            event.dataTransfer.setData("text/plain", pill.dataset.eventId);
            pill.classList.add("dragging");
        });
        pill.addEventListener("dragend", () => pill.classList.remove("dragging"));
    });

    const cells = document.querySelectorAll(".month-cell");
    cells.forEach(cell => {
        cell.addEventListener("dragover", event => {
            event.preventDefault();
            cell.classList.add("drag-over");
        });
        cell.addEventListener("dragleave", () => cell.classList.remove("drag-over"));
        cell.addEventListener("drop", event => {
            event.preventDefault();
            cell.classList.remove("drag-over");
            const eventId = event.dataTransfer.getData("text/plain");
            const newDate = cell.dataset.date;
            const evt = calState.events.find(e => e.id === eventId);
            if (evt && newDate) {
                evt.date = newDate;
                calSaveEvents();
                calRender();
            }
        });
    });
}

/* =========================================================
   QUICK-PEEK POPOVER
   ========================================================= */
function calAttachPillClicks() {
    document.querySelectorAll("[data-event-id]").forEach(el => {
        el.addEventListener("click", event => {
            event.stopPropagation();
            const evt = calState.events.find(e => e.id === el.dataset.eventId);
            if (evt) calOpenPopover(evt, event.clientX, event.clientY);
        });
    });
}

function calOpenPopover(evt, x, y) {
    const popover = document.getElementById("eventPopover");
    const overlay = document.getElementById("popoverOverlay");
    const header = document.getElementById("popoverHeader");
    const meta = CAL_TYPE_META[evt.type] || { label: "Event", pillClass: "pill-sla" };

    document.getElementById("popoverTitle").textContent = evt.title;
    document.getElementById("popoverDate").textContent = evt.time ? `${evt.date} at ${evt.time}` : evt.date;
    document.getElementById("popoverType").textContent = meta.label;
    document.getElementById("popoverSummary").textContent = evt.summary || "No additional details.";

    const ticketLink = document.getElementById("popoverTicketLink");
    const ticketText = document.getElementById("popoverTicketText");
    if (evt.ticketId) {
        ticketText.textContent = `Link to Ticket #${evt.ticketId}`;
        ticketLink.style.display = "inline-flex";
        ticketLink.onclick = e => { e.preventDefault(); window.location.href = `inbox.html#${evt.ticketId}`; };
    } else {
        ticketLink.style.display = "none";
    }

    const colorMap = { "pill-pto": "#16a34a", "pill-maintenance": "#dc2626", "pill-sla": "#2563eb", "pill-onboarding": "#d97706", "pill-offboarding": "#6b7280" };
    header.style.background = colorMap[meta.pillClass] || "#2b1b38";

    const popW = 280;
    const maxLeft = window.innerWidth - popW - 16;
    popover.style.left = Math.min(Math.max(x - popW / 2, 16), maxLeft) + "px";
    const estimatedTop = y + 180 > window.innerHeight ? y - 200 : y + 16;
    popover.style.top = Math.max(estimatedTop, 16) + "px";

    popover.classList.add("open");
    overlay.classList.add("open");
}

function calClosePopover() {
    document.getElementById("eventPopover").classList.remove("open");
    document.getElementById("popoverOverlay").classList.remove("open");
}

/* =========================================================
   INIT
   ========================================================= */
async function initializeCalendarPage() {
    const calBody = document.getElementById("calBody");
    if (!calBody) return;

    calState.events = await calLoadEvents();
    calRender();

    document.getElementById("calPrevBtn").addEventListener("click", () => {
        if (calState.view === "month") calState.date = new Date(calState.date.getFullYear(), calState.date.getMonth() - 1, 1);
        else if (calState.view === "week") calState.date = calAddDays(calState.date, -7);
        else calState.date = calAddDays(calState.date, -1);
        calRender();
    });

    document.getElementById("calNextBtn").addEventListener("click", () => {
        if (calState.view === "month") calState.date = new Date(calState.date.getFullYear(), calState.date.getMonth() + 1, 1);
        else if (calState.view === "week") calState.date = calAddDays(calState.date, 7);
        else calState.date = calAddDays(calState.date, 1);
        calRender();
    });

    document.getElementById("calTodayBtn").addEventListener("click", () => {
        calState.date = new Date();
        calRender();
    });

    document.querySelectorAll(".view-toggle-btn").forEach(btn => {
        if (btn.dataset.view === calState.view) btn.classList.add("active");
        btn.addEventListener("click", () => {
            document.querySelectorAll(".view-toggle-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            calState.view = btn.dataset.view;
            calRender();
        });
    });

    document.querySelectorAll(".cal-filter").forEach(checkbox => {
        checkbox.addEventListener("change", () => {
            const type = checkbox.dataset.type;
            if (checkbox.checked) calState.activeFilters.add(type);
            else calState.activeFilters.delete(type);
            calRender();
        });
    });

    document.getElementById("popoverCloseBtn").addEventListener("click", calClosePopover);
    document.getElementById("popoverOverlay").addEventListener("click", calClosePopover);

    document.getElementById("syncOutlookBtn").addEventListener("click", () => {
        alert("Syncing approved PTO and deadlines with Outlook Calendar...");
    });
    document.getElementById("exportGoogleBtn").addEventListener("click", () => {
        alert("Exporting calendar events to Google Calendar...");
    });
}
