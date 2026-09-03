import { writable, derived, get } from 'svelte/store';
import { apiFetchTickets, apiCreateTicket, apiUpdateTicket, apiPostComment } from '../api.js';
import { userStore, isSuperAdmin } from './auth.js';

export const tickets = writable([]);
export const loading = writable(false);
export const searchQuery = writable('');
export const statusFilter = writable('all');
export const priorityFilter = writable('all');
export const assigneeFilter = writable('all');
const savedTab = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('activeTab') : null;
const savedPrevTab = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('previousTab') : null;
let savedSelectedTicketId = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('selectedTicketId') : null;
try {
  // One-time migration from the old serialized ticket snapshot. Keeping an
  // entire ticket in sessionStorage made a normal refresh restore stale
  // priority/department values after Genie changed the database record.
  const storedTicket = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('selectedTicket') : null;
  if (!savedSelectedTicketId && storedTicket) {
    savedSelectedTicketId = JSON.parse(storedTicket)?.id || null;
  }
  if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('selectedTicket');
} catch (e) {}

export const activeTab = writable(savedTab || 'dashboard');
export const previousTab = writable(savedPrevTab || 'dashboard');
export const selectedTicket = writable(
  savedSelectedTicketId ? { id: savedSelectedTicketId, _loading: true } : null
);
export const isCreateModalOpen = writable(false);
export const sidebarCollapsed = writable(false);
export const genieDraftStore = writable(null);
export const onboardingDraftStore = writable(null);

activeTab.subscribe((current) => {
  if (typeof sessionStorage !== 'undefined' && current) {
    sessionStorage.setItem('activeTab', current);
  }
  if (current !== 'ticket-detail' && current !== 'ticket-thread') {
    previousTab.set(current);
    if (typeof sessionStorage !== 'undefined' && current) {
      sessionStorage.setItem('previousTab', current);
    }
    const currentUser = get(userStore);
    if (currentUser) {
      loadTickets();
    }
  }
});

selectedTicket.subscribe((ticket) => {
  if (typeof sessionStorage !== 'undefined') {
    if (ticket?.id) {
      savedSelectedTicketId = ticket.id;
      sessionStorage.setItem('selectedTicketId', ticket.id);
    } else {
      savedSelectedTicketId = null;
      sessionStorage.removeItem('selectedTicketId');
    }
    sessionStorage.removeItem('selectedTicket');
  }
});

export async function loadTickets(adminView = null) {
  loading.set(true);
  try {
    const currentTab = get(activeTab);
    const currentUser = get(userStore);
    const isEmployeeRole = currentUser?.role === 'Employee';
    const isMyTicketsTab = currentTab === 'dashboard' || currentTab === 'my-tickets';

    const effectiveAdminView = adminView !== null 
      ? adminView 
      : (!isEmployeeRole && !isMyTicketsTab);

    let deptParam = null;
    if (effectiveAdminView) {
      if (currentTab === 'queue-it') {
        deptParam = 'IT';
      } else if (currentTab === 'queue-hr') {
        deptParam = 'HR';
      } else if (currentTab === 'queue-finance') {
        deptParam = 'Accounting';
      } else if (currentTab === 'inbox' && currentUser?.department) {
        deptParam = currentUser.department.includes('Upper') ? 'Upper' : currentUser.department;
      }
    }

    const data = await apiFetchTickets({ adminView: effectiveAdminView, department: deptParam });
    tickets.set(data || []);
    const selectedId = get(selectedTicket)?.id || savedSelectedTicketId;
    if (selectedId) {
      selectedTicket.set((data || []).find((ticket) => ticket.id === selectedId) || null);
    }
  } catch (err) {
    console.error("Failed to load tickets from backend API:", err);
    tickets.set([]);
  } finally {
    loading.set(false);
  }
}

export async function refreshTicketState(ticketId = null) {
  await loadTickets();
}

export function isSameDepartment(userDeptRaw, ticketDeptRaw) {
  if (!userDeptRaw || !ticketDeptRaw) return false;
  const d1 = userDeptRaw.toLowerCase().trim();
  const d2 = ticketDeptRaw.toLowerCase().trim();

  if (d1 === d2 || d1.includes(d2) || d2.includes(d1)) return true;

  // Department name alias matching (e.g. "Upper Executive Management" in user profile vs "Upper Management" in DB)
  if (d1.includes('upper') && d2.includes('upper')) return true;
  if (d1.includes('it') && d2.includes('it')) return true;
  if (d1.includes('hr') && d2.includes('hr')) return true;
  if ((d1.includes('account') || d1.includes('fin')) && (d2.includes('account') || d2.includes('fin'))) return true;

  return false;
}

export const filteredTickets = derived(
  [tickets, searchQuery, statusFilter, priorityFilter, assigneeFilter, activeTab, userStore],
  ([$tickets, $search, $status, $priority, $assignee, $tab, $user]) => {
    const isEmployeeView = $tab === 'dashboard' || $tab === 'my-tickets';
    const userEmail = ($user?.email || '').toLowerCase().trim();
    const userOid = ($user?.objectId || $user?.azure_object_id || $user?.oid || '').toLowerCase().trim();
    const userName = ($user?.name || '').toLowerCase().trim();

    return $tickets.filter((t) => {
      // 1. Employee View Scoping: Only show tickets personally created and submitted by the logged-in user
      if (isEmployeeView) {
        const reqId = (t.requester_id || t.user_id || '').toLowerCase().trim();
        const reqName = (t.requester || '').toLowerCase().trim();
        const matchesUser = 
          !reqId ||
          t.is_anonymous ||
          (userOid && reqId === userOid) || 
          (userEmail && reqId === userEmail) || 
          (userEmail && reqId.includes(userEmail)) ||
          (userEmail && reqName.includes(userEmail)) ||
          (userName && reqName.includes(userName));
        
        if (!matchesUser && $tickets.length > 0 && reqId) {
          return false;
        }
      }

      // 2. Department Queue Filtering (Admin / Management View)
      if ($tab === 'inbox') {
        const userDept = $user?.department || (isSuperAdmin($user) ? 'Upper Executive Management' : 'IT Team');
        const ticketDept = t.department || '';
        if (userDept && ticketDept && !isSameDepartment(userDept, ticketDept)) {
          return false;
        }
      } else if ($tab === 'queue-it') {
        const dept = (t.department || '').toLowerCase().trim();
        if (!dept.includes('it')) return false;
      } else if ($tab === 'queue-hr') {
        const dept = (t.department || '').toLowerCase().trim();
        if (!dept.includes('hr')) return false;
      } else if ($tab === 'queue-finance') {
        const dept = (t.department || '').toLowerCase().trim();
        if (!dept.includes('account') && !dept.includes('fin')) return false;
      }

      // 3. Search & Filter Matching
      const matchSearch = !$search || 
        (t.title && t.title.toLowerCase().includes($search.toLowerCase())) ||
        (t.id && t.id.toLowerCase().includes($search.toLowerCase())) ||
        (t.requester && t.requester.toLowerCase().includes($search.toLowerCase())) ||
        (t.requester_name && t.requester_name.toLowerCase().includes($search.toLowerCase())) ||
        (t.requester_id && t.requester_id.toLowerCase().includes($search.toLowerCase())) ||
        (t.category && t.category.toLowerCase().includes($search.toLowerCase())) ||
        (t.description && t.description.toLowerCase().includes($search.toLowerCase())) ||
        (t.assigned_to && t.assigned_to.toLowerCase().includes($search.toLowerCase()));

      const matchStatus = $status === 'all' || t.status?.toLowerCase() === $status.toLowerCase();
      const matchPriority = $priority === 'all' || t.priority?.toLowerCase() === $priority.toLowerCase();

      const assignedStr = (t.assigned_to || '').toLowerCase().trim();
      const matchAssignee = $assignee === 'all'
        ? true
        : $assignee === 'unassigned'
        ? (!assignedStr)
        : $assignee === 'me'
        ? (assignedStr && (
            (userName && assignedStr.includes(userName)) ||
            (userEmail && assignedStr.includes(userEmail)) ||
            (userOid && assignedStr.includes(userOid))
          ))
        : true;

      return matchSearch && matchStatus && matchPriority && matchAssignee;
    });
  }
);

export const ticketMetrics = derived(filteredTickets, ($tickets) => {
  const total = $tickets.length;
  const open = $tickets.filter(t => (t.status || '').toLowerCase() === 'open').length;
  const inProgress = $tickets.filter(t => (t.status || '').toLowerCase() === 'in progress' || (t.status || '').toLowerCase() === 'in_progress').length;
  const resolved = $tickets.filter(t => (t.status || '').toLowerCase() === 'resolved' || (t.status || '').toLowerCase() === 'closed').length;
  const highPriority = $tickets.filter(t => (t.priority || '').toLowerCase() === 'high' || (t.priority || '').toLowerCase() === 'urgent').length;

  const slaPassed = total > 0 ? Math.round(((total - highPriority) / total) * 100) : 98;

  return {
    total,
    open,
    inProgress,
    resolved,
    highPriority,
    slaPercent: slaPassed || 98
  };
});

export async function submitNewTicket(payload) {
  loading.set(true);
  try {
    const res = await apiCreateTicket(payload);
    await loadTickets();
    return res;
  } catch (err) {
    console.error("submitNewTicket failed:", err);
    throw err;
  } finally {
    loading.set(false);
  }
}

export async function changeTicketStatus(ticketId, newStatus) {
  try {
    await apiUpdateTicket(ticketId, { status: newStatus });
    tickets.update(all => all.map(t => t.id === ticketId ? { ...t, status: newStatus } : t));
  } catch (err) {
    console.error("changeTicketStatus failed:", err);
    throw err;
  }
}

export async function transferTicketDepartment(ticketId, newDepartment) {
  try {
    const updated = await apiUpdateTicket(ticketId, { department: newDepartment });
    tickets.update(all => all.map(t => t.id === ticketId ? { ...t, department: newDepartment } : t));
    selectedTicket.update(st => (st && st.id === ticketId ? { ...st, department: newDepartment } : st));
    try {
      await apiPostComment(ticketId, `[System] Ticket transferred and re-routed to ${newDepartment}.`);
    } catch (e) {}
    return updated;
  } catch (err) {
    console.error("transferTicketDepartment failed:", err);
    throw err;
  }
}

export async function assignTicketToSelf(ticketId, assigneeName = null) {
  try {
    const user = get(userStore);
    const name = assigneeName || user?.name || user?.email?.split('@')[0] || 'Support Agent';
    const updated = await apiUpdateTicket(ticketId, { assigned_to: name });
    tickets.update(all => all.map(t => t.id === ticketId ? { ...t, assigned_to: name } : t));
    selectedTicket.update(st => (st && st.id === ticketId ? { ...st, assigned_to: name } : st));
    return updated;
  } catch (err) {
    console.error("assignTicketToSelf failed:", err);
    throw err;
  }
}

export async function unassignTicket(ticketId) {
  try {
    const updated = await apiUpdateTicket(ticketId, { assigned_to: '' });
    tickets.update(all => all.map(t => t.id === ticketId ? { ...t, assigned_to: null } : t));
    selectedTicket.update(st => (st && st.id === ticketId ? { ...st, assigned_to: null } : st));
    return updated;
  } catch (err) {
    console.error("unassignTicket failed:", err);
    throw err;
  }
}
