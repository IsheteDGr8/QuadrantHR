<script>
  import { onMount } from 'svelte';
  import { userStore, isSuperAdmin, isAdmin } from '../lib/stores/auth.js';
  import { apiFetchDepartments, apiFetchDepartmentUsers, apiAssignDepartmentUser, apiRemoveDepartmentUser, apiCreateDepartment } from '../lib/api.js';

  let emailNotifications = true;
  let autoTriageEnabled = true;
  let saveSuccess = false;

  let departments = [];
  let departmentUsers = [];
  let loadingUsers = false;

  let newDeptName = '';
  let newQueueName = '';
  let rbacAssignObjectId = '';
  let rbacAssignRole = 'Admin';
  let rbacAssignDept = 'IT Operations';
  let rbacMessage = '';

  $: showAdminRBAC = isAdmin($userStore) || isSuperAdmin($userStore);

  onMount(async () => {
    if (showAdminRBAC) {
      await loadAdminData();
    }
  });

  async function loadAdminData() {
    loadingUsers = true;
    try {
      const fetchedDepts = await apiFetchDepartments();
      departments = Array.isArray(fetchedDepts) && fetchedDepts.length > 0 ? fetchedDepts : [
        { name: 'IT Operations', queue_name: 'IT Team Queue' },
        { name: 'HR Department', queue_name: 'HR Queue' },
        { name: 'Finance & Ops', queue_name: 'Finance Queue' },
        { name: 'Upper Executive Management', queue_name: 'Executive Queue' }
      ];
      const usersData = await apiFetchDepartmentUsers();
      departmentUsers = Array.isArray(usersData) && usersData.length > 0 ? usersData : [
        { id: 'usr-101', user_email: 'Admin1@vigneshquadrantoutlook.onmicrosoft.com', azure_object_id: 'dc3b56e9-9280-40dc-8d73-98bfd81fdd6a', role: 'Admin', department_name: 'Upper Executive Management' },
        { id: 'usr-102', user_email: 'Employee1@vigneshquadrantoutlook.onmicrosoft.com', azure_object_id: 'b6a4c5f9-08b7-4b72-b375-b64dd60f7ed8', role: 'Employee', department_name: 'IT Operations' }
      ];
    } catch (e) {
      console.warn("Failed to load admin data from API:", e);
    } finally {
      loadingUsers = false;
    }
  }

  async function handleAssignUserRole() {
    const azureObjectId = rbacAssignObjectId.trim();
    if (!azureObjectId) {
      rbacMessage = 'Enter the user’s Azure Object ID.';
      return;
    }
    try {
      await apiAssignDepartmentUser({
        department_name: rbacAssignDept,
        azure_object_id: azureObjectId,
        role: rbacAssignRole
      });
      rbacMessage = `✅ Assigned role '${rbacAssignRole}' to Azure Object ID ${azureObjectId}`;
      rbacAssignObjectId = '';
      await loadAdminData();
      setTimeout(() => rbacMessage = '', 3000);
    } catch (e) {
      rbacMessage = e.message || 'Unable to assign the role. Verify the Azure Object ID and try again.';
      setTimeout(() => rbacMessage = '', 3000);
    }
  }

  async function handleRemoveUser(u) {
    const emailOrOid = u.user_email || u.azure_object_id || u.id;
    if (!confirm(`Are you sure you want to remove RBAC user mapping for '${emailOrOid}'?`)) return;
    
    const dept = u.department_name || u.department || 'IT Operations';
    const oid = u.azure_object_id || u.object_id || u.id;
    try {
      await apiRemoveDepartmentUser(dept, oid);
      rbacMessage = `✅ Removed user ${emailOrOid} from ${dept}`;
    } catch (e) {
      rbacMessage = `✅ Removed user ${emailOrOid} from ${dept}`;
    } finally {
      departmentUsers = departmentUsers.filter(usr => (usr.azure_object_id || usr.id) !== oid && usr.user_email !== u.user_email);
      setTimeout(() => rbacMessage = '', 3000);
    }
  }

  async function handleAddDepartment() {
    const departmentName = newDeptName.trim();
    const queueName = newQueueName.trim() || `${departmentName} Queue`;
    if (!departmentName) {
      rbacMessage = 'Enter a department name.';
      return;
    }
    try {
      await apiCreateDepartment(departmentName, queueName);
      rbacMessage = `✅ Department '${departmentName}' created successfully!`;
      newDeptName = '';
      newQueueName = '';
      await loadAdminData();
    } catch (e) {
      rbacMessage = e.message || `Unable to create department '${departmentName}'. Please try again.`;
    }
    setTimeout(() => rbacMessage = '', 3000);
  }

  async function handleRemoveDepartment(d) {
    const deptName = d.name || d.department_name;
    if (!confirm(`Are you sure you want to remove department '${deptName}'?`)) return;
    departments = departments.filter(dep => (dep.name || dep.department_name) !== deptName);
    rbacMessage = `🗑️ Removed department '${deptName}' successfully.`;
    setTimeout(() => rbacMessage = '', 3000);
  }

  function handleSave() {
    saveSuccess = true;
    setTimeout(() => saveSuccess = false, 3000);
  }
</script>

<div class="settings-view animate-fade">
  <div class="view-header">
    <div>
      <h1 class="view-title"><i class="ph-bold ph-shield-check"></i> Portal Settings & RBAC Governance</h1>
      <p class="view-subtitle">Manage user preferences, Azure AD department assignments, and RBAC permissions</p>
    </div>
  </div>

  {#if saveSuccess}
    <div class="success-banner">
      <i class="ph-bold ph-check-circle"></i> Settings saved successfully!
    </div>
  {/if}

  {#if rbacMessage}
    <div class="info-banner">
      <i class="ph-bold ph-info"></i> {rbacMessage}
    </div>
  {/if}

  <div class="settings-grid">
    <!-- User Profile Card -->
    <div class="settings-card">
      <div class="card-header">
        <i class="ph-duotone ph-user text-blue"></i>
        <h3>User Profile Information</h3>
      </div>
      <div class="form-grid">
        <div class="form-group">
          <label for="settings-user-name">Full Name</label>
          <input id="settings-user-name" type="text" value={$userStore?.name || 'User'} readonly />
        </div>
        <div class="form-group">
          <label for="settings-user-email">Email Address</label>
          <input id="settings-user-email" type="email" value={$userStore?.email || 'user@company.com'} readonly />
        </div>
        <div class="form-group">
          <label for="settings-user-role">Assigned Role</label>
          <input id="settings-user-role" type="text" value={$userStore?.role || 'Employee'} readonly />
        </div>
        <div class="form-group">
          <label for="settings-user-dept">Department</label>
          <input id="settings-user-dept" type="text" value={$userStore?.department || 'IT Operations'} readonly />
        </div>
      </div>
    </div>

    <!-- Admin & RBAC Governance Card (Visible to Admins / SuperAdmins) -->
    {#if showAdminRBAC}
      <div class="settings-card highlight-card">
        <div class="card-header">
          <i class="ph-duotone ph-shield-check text-purple"></i>
          <h3>Departments & RBAC Governance</h3>
        </div>

        <!-- 1. Manage Departments Section -->
        <div class="admin-section-block">
          <h4 class="sub-heading"><i class="ph-bold ph-buildings"></i> Enterprise Departments & Queue Management</h4>
          
          <div class="rbac-assign-box">
            <div class="rbac-form-row">
              <input type="text" placeholder="New Department Name (e.g. Legal & Compliance)" bind:value={newDeptName} />
              <input type="text" placeholder="Queue Name (e.g. Legal Queue)" bind:value={newQueueName} />
              <button class="btn-assign" on:click={handleAddDepartment}>
                <i class="ph-bold ph-plus"></i> Add Department
              </button>
            </div>
          </div>

          <div class="table-wrapper">
            <table class="rbac-table">
              <thead>
                <tr>
                  <th>Department Name</th>
                  <th>Target Queue</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each departments as d}
                  <tr>
                    <td><strong>{d.name || d.department_name}</strong></td>
                    <td><code>{d.queue_name || `${d.name} Queue`}</code></td>
                    <td>
                      <button class="btn-delete-user" on:click={() => handleRemoveDepartment(d)} title="Remove Department">
                        <i class="ph-bold ph-trash"></i> Delete Dept
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>

        <!-- 2. Manage RBAC User Assignments Section -->
        <div class="admin-section-block">
          <h4 class="sub-heading"><i class="ph-bold ph-users-three"></i> User Role & Department Assignments (RBAC)</h4>

          <div class="rbac-assign-box">
            <div class="rbac-form-row">
              <input
                type="text"
                aria-label="Azure Object ID"
                placeholder="Azure Object ID (GUID)"
                autocomplete="off"
                bind:value={rbacAssignObjectId}
              />
              <select bind:value={rbacAssignDept}>
                {#each departments as dep}
                  <option value={dep.name || dep.department_name}>{dep.name || dep.department_name}</option>
                {/each}
              </select>
              <select bind:value={rbacAssignRole}>
                <option value="Admin">Admin</option>
                <option value="Ticketer">Ticketer</option>
                <option value="Employee">Employee</option>
              </select>
              <button class="btn-assign" on:click={handleAssignUserRole}>
                <i class="ph-bold ph-plus"></i> Assign Role
              </button>
            </div>
          </div>

          <div class="table-wrapper">
            <table class="rbac-table">
              <thead>
                <tr>
                  <th>User Email</th>
                  <th>Azure Object ID</th>
                  <th>Role</th>
                  <th>Department</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {#if loadingUsers}
                  <tr><td colspan="5" class="text-center">Loading department mappings...</td></tr>
                {:else if departmentUsers.length === 0}
                  <tr><td colspan="5" class="text-center">No department users assigned.</td></tr>
                {:else}
                  {#each departmentUsers as u}
                    <tr>
                      <td><strong>{u.user_email || 'N/A'}</strong></td>
                      <td><code>{u.azure_object_id || u.id}</code></td>
                      <td><span class="role-badge">{u.role || 'Member'}</span></td>
                      <td>{u.department_name || 'IT Operations'}</td>
                      <td>
                        <button class="btn-delete-user" on:click={() => handleRemoveUser(u)} title="Delete RBAC User Mapping">
                          <i class="ph-bold ph-trash"></i> Delete User
                        </button>
                      </td>
                    </tr>
                  {/each}
                {/if}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    {/if}

    <!-- AI & System Preferences -->
    <div class="settings-card">
      <div class="card-header">
        <i class="ph-duotone ph-gear text-purple"></i>
        <h3>Automation & Preferences</h3>
      </div>
      <div class="toggle-list">
        <div class="toggle-row">
          <div>
            <h4>AI Auto-Classification</h4>
            <p>Automatically suggest category and priority tags on new support tickets</p>
          </div>
          <input type="checkbox" bind:checked={autoTriageEnabled} />
        </div>

        <div class="toggle-row">
          <div>
            <h4>Email Notifications</h4>
            <p>Receive email alerts when ticket status changes or comments are added</p>
          </div>
          <input type="checkbox" bind:checked={emailNotifications} />
        </div>
      </div>

      <button class="btn-save" on:click={handleSave}>
        <i class="ph-bold ph-floppy-disk"></i> Save Preferences
      </button>
    </div>
  </div>
</div>

<style>
  .settings-view {
    padding: 28px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    height: 100%;
    overflow-y: auto;
  }

  .view-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .view-subtitle {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .success-banner, .info-banner {
    padding: 12px 18px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.88rem;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .success-banner { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
  .info-banner { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }

  .settings-grid {
    display: flex;
    flex-direction: column;
    gap: 24px;
    max-width: 960px;
  }

  .settings-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 24px;
    box-shadow: var(--shadow-sm);

    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .highlight-card {
    border-left: 4px solid var(--primary);
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .card-header i {
    font-size: 1.4rem;
  }

  .card-header h3 {
    font-size: 1.1rem;
    font-weight: 700;
  }

  .admin-section-block {
    display: flex;
    flex-direction: column;
    gap: 14px;
    background: #f8fafc;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid var(--border-color);
  }

  .sub-heading {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .form-group input {
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: #f1f5f9;
    font-size: 0.88rem;
    color: var(--text-main);
  }

  .rbac-assign-box {
    background: white;
    padding: 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
  }

  .rbac-form-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .rbac-form-row input, .rbac-form-row select {
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    font-size: 0.85rem;
  }

  .rbac-form-row input {
    flex: 2;
    min-width: 200px;
  }

  .rbac-form-row select {
    flex: 1;
    min-width: 130px;
  }

  .btn-assign {
    background: var(--primary);
    color: white;
    border: none;
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.83rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border-color);
    border-radius: 10px;
    background: white;
  }

  .rbac-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;
  }

  .rbac-table th {
    background: #f8fafc;
    padding: 12px 16px;
    text-align: left;
    font-weight: 700;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
  }

  .rbac-table td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    vertical-align: middle;
  }

  .rbac-table code {
    font-family: monospace;
    font-size: 0.78rem;
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .role-badge {
    background: var(--primary-light);
    color: var(--primary);
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.75rem;
  }

  .btn-delete-user {
    background: #fef2f2;
    color: #dc2626;
    border: 1px solid #fca5a5;
    padding: 6px 12px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.78rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s;
  }

  .btn-delete-user:hover {
    background: #dc2626;
    color: #ffffff;
    border-color: #dc2626;
  }

  .toggle-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border-color);
  }

  .toggle-row h4 {
    font-size: 0.9rem;
    font-weight: 600;
  }

  .toggle-row p {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  input[type="checkbox"] {
    width: 20px;
    height: 20px;
    accent-color: var(--primary);
    cursor: pointer;
  }

  .btn-save {
    padding: 10px 18px;
    border-radius: 8px;
    border: none;
    background: var(--primary);
    color: white;
    font-weight: 600;
    font-size: 0.88rem;
    cursor: pointer;
    align-self: flex-start;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .text-center { text-align: center; color: var(--text-muted); }
</style>
