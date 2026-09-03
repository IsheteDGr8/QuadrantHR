/* =========================================================
   TICKETGENIE THEME & COMMON UI UTILITIES
   Shared UI functions (Dark Mode, Toasts, Input Escaping)
   ========================================================= */

function escapeHTML(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

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

document.addEventListener("DOMContentLoaded", () => {
    initDarkMode();
    initSidebarToggle();
});

Object.assign(window, {
    escapeHTML,
    showNotification,
    showFormError,
    showSuccessMessage,
    initDarkMode,
    initSidebarToggle
});
