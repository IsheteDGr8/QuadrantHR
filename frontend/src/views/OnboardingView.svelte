<script>
  import { onMount } from 'svelte';
  import {
    apiAddOnboardingTicket,
    apiFetchOnboardingCase,
    apiFetchOnboardingCases,
    apiStartOnboarding,
    apiSuggestOnboardingPlan
  } from '../lib/api.js';
  import { activeTab, onboardingDraftStore, previousTab, selectedTicket } from '../lib/stores/tickets.js';

  const departments = ['IT Team', 'HR Team', 'Accounting Team', 'Workplace Operations Team', 'Upper Management'];
  const priorities = ['Low', 'Medium', 'High', 'Critical'];
  const categories = {
    'IT Team': ['Laptop Requests', 'Identity and Access Management', 'Software Licensing', 'Other IT Request'],
    'HR Team': ['Employee Relationships', 'Onboarding and Offboarding', 'Benefits Inquiries', 'Other HR Request'],
    'Accounting Team': ['Company Card Management', 'Reimbursement Requests', 'Business Development Management', 'Other Accounting Request'],
    'Workplace Operations Team': ['Maintenance', 'Badge Registration', 'Office Equipment Issues', 'Other Workplace Request'],
    'Upper Management': ['High-Impact Company Conflict', 'Executive Review', 'Company-Wide Issue', 'Other Management Issue']
  };

  let cases = [];
  let mode = 'list';
  let loading = true;
  let working = false;
  let errorMsg = '';
  let selectedCase = null;
  let plan = [];
  let employee = emptyEmployee();
  let showCustomForm = false;
  let customTicket = emptyTicket();

  $: if ($onboardingDraftStore) {
    employee = { ...emptyEmployee(), ...$onboardingDraftStore };
    onboardingDraftStore.set(null);
    plan = [];
    errorMsg = '';
    mode = 'create';
  }

  function emptyEmployee() {
    return { employee_name: '', employee_email: '', job_title: '', employee_department: '', manager: '', location: '', visa_status: '', start_date: '' };
  }

  function emptyTicket() {
    return {
      title: '',
      description: '',
      department: 'IT Team',
      category: 'Other IT Request',
      priority: 'Medium',
      due_date: employee.start_date || ''
    };
  }

  onMount(loadCases);

  async function loadCases() {
    loading = true;
    errorMsg = '';
    try {
      cases = await apiFetchOnboardingCases();
    } catch (err) {
      errorMsg = err.message || 'Unable to load onboarding cases.';
    } finally {
      loading = false;
    }
  }

  function beginCreate() {
    employee = emptyEmployee();
    plan = [];
    errorMsg = '';
    mode = 'create';
  }

  async function generatePlan() {
    if (!employee.employee_name || !employee.employee_email || !employee.job_title || !employee.employee_department || !employee.start_date) {
      errorMsg = 'Complete all required employee fields before generating a plan.';
      return;
    }
    working = true;
    errorMsg = '';
    try {
      const result = await apiSuggestOnboardingPlan(employee.job_title, employee.start_date);
      plan = result.tickets || [];
      mode = 'review';
    } catch (err) {
      errorMsg = err.message || 'Unable to generate the onboarding plan.';
    } finally {
      working = false;
    }
  }

  function updatePlanItem(index, field, value) {
    plan[index] = { ...plan[index], [field]: value };
    if (field === 'department') {
      plan[index].category = categories[value][categories[value].length - 1];
    }
    plan = [...plan];
  }

  function removePlanItem(index) {
    plan = plan.filter((_, itemIndex) => itemIndex !== index);
  }

  function addCustomToPlan() {
    if (!customTicket.title.trim() || !customTicket.description.trim()) {
      errorMsg = 'Custom tickets need a title and description.';
      return;
    }
    plan = [...plan, { ...customTicket, id: `custom-${Date.now()}`, selected: true }];
    customTicket = emptyTicket();
    showCustomForm = false;
    errorMsg = '';
  }

  async function startOnboarding() {
    const approved = plan.filter(item => item.selected).map(({ id, selected, ...item }) => item);
    if (!approved.length) {
      errorMsg = 'Select at least one ticket before starting onboarding.';
      return;
    }
    working = true;
    errorMsg = '';
    try {
      selectedCase = await apiStartOnboarding({ ...employee, tickets: approved });
      cases = [selectedCase, ...cases];
      mode = 'detail';
    } catch (err) {
      errorMsg = err.message || 'Unable to start onboarding.';
    } finally {
      working = false;
    }
  }

  async function openCase(item) {
    working = true;
    errorMsg = '';
    try {
      selectedCase = await apiFetchOnboardingCase(item.id);
      mode = 'detail';
    } catch (err) {
      errorMsg = err.message || 'Unable to load onboarding details.';
    } finally {
      working = false;
    }
  }

  async function addTicketAfterStart() {
    if (!customTicket.title.trim() || !customTicket.description.trim()) {
      errorMsg = 'Custom tickets need a title and description.';
      return;
    }
    working = true;
    try {
      await apiAddOnboardingTicket(selectedCase.id, customTicket);
      selectedCase = await apiFetchOnboardingCase(selectedCase.id);
      customTicket = emptyTicket();
      showCustomForm = false;
      await loadCases();
      mode = 'detail';
    } catch (err) {
      errorMsg = err.message || 'Unable to add the onboarding ticket.';
    } finally {
      working = false;
    }
  }

  function openTicket(ticket) {
    $selectedTicket = ticket;
    $previousTab = 'onboarding';
    $activeTab = 'ticket-detail';
  }

  function backToList() {
    mode = 'list';
    selectedCase = null;
    showCustomForm = false;
    loadCases();
  }

  function healthClass(health) {
    return (health || '').toLowerCase().replaceAll(' ', '-');
  }
</script>

<div class="onboarding-view animate-fade">
  <div class="view-header">
    <div>
      <h1 class="view-title"><i class="ph-bold ph-user-plus"></i> Onboarding Pipeline</h1>
      <p class="view-subtitle">Plan new-hire work, create real department tickets, and track readiness.</p>
    </div>
    {#if mode === 'list'}
      <button class="btn-primary" on:click={beginCreate}><i class="ph-bold ph-plus"></i> Create New Onboarding</button>
    {:else}
      <button class="btn-secondary" on:click={backToList}><i class="ph-bold ph-arrow-left"></i> All Onboardings</button>
    {/if}
  </div>

  {#if errorMsg}<div class="error-banner"><i class="ph-bold ph-warning-circle"></i> {errorMsg}</div>{/if}

  {#if mode === 'list'}
    <div class="summary-grid">
      <div class="summary-card"><span>Active Cases</span><strong>{cases.filter(item => item.health !== 'Complete').length}</strong></div>
      <div class="summary-card risk"><span>At Risk / Blocked</span><strong>{cases.filter(item => ['At Risk', 'Blocked'].includes(item.health)).length}</strong></div>
      <div class="summary-card complete"><span>Completed</span><strong>{cases.filter(item => item.health === 'Complete').length}</strong></div>
    </div>
    <div class="card-box">
      {#if loading}
        <div class="empty-state"><i class="ph-bold ph-spinner animate-spin"></i> Loading onboarding pipeline...</div>
      {:else if !cases.length}
        <div class="empty-state"><i class="ph-duotone ph-users-three"></i><strong>No onboarding cases yet</strong><span>Create the first reviewed onboarding plan.</span></div>
      {:else}
        <div class="case-list">
          {#each cases as item}
            <button class="case-row" class:resolved={item.health === 'Complete'} on:click={() => openCase(item)}>
              <div><span class="case-id">{item.id}</span><strong>{item.employee_name}</strong><small>{item.role} · {item.department}</small></div>
              <div><small>Starts</small><strong>{item.start_date}</strong></div>
              <div class="progress-block"><div><span>{item.completed_tickets} / {item.total_tickets} complete</span><strong>{item.progress_percentage}%</strong></div><div class="progress-track"><span style={`width:${item.progress_percentage}%`}></span></div></div>
              <span class={`health-badge ${healthClass(item.health)}`}>{item.health}</span>
              <i class="ph-bold ph-caret-right"></i>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {:else if mode === 'create'}
    <div class="card-box form-card">
      <div class="section-heading"><span>1</span><div><h2>New employee details</h2><p>Required fields are used to generate an appropriate onboarding plan.</p></div></div>
      <div class="form-grid">
        <label>Employee Name *<input bind:value={employee.employee_name} placeholder="Priya Shah" /></label>
        <label>Employee Email *<input type="email" bind:value={employee.employee_email} placeholder="priya@company.com" /></label>
        <label>Job Title *<input bind:value={employee.job_title} placeholder="Data Analyst" /></label>
        <label>Employee Department *<input bind:value={employee.employee_department} placeholder="Analytics" /></label>
        <label>Manager<input bind:value={employee.manager} placeholder="Manager name" /></label>
        <label>Location<input bind:value={employee.location} placeholder="Seattle / Remote" /></label>
        <label>Start Date *<input type="date" bind:value={employee.start_date} /></label>
        <label>Work Authorization / Notes<input bind:value={employee.visa_status} placeholder="Optional" /></label>
      </div>
      <div class="footer-actions"><button class="btn-primary" on:click={generatePlan} disabled={working}>{working ? 'Generating...' : 'Generate Onboarding Plan'} <i class="ph-bold ph-arrow-right"></i></button></div>
    </div>
  {:else if mode === 'review'}
    <div class="review-header card-box">
      <div><span class="eyebrow">REVIEW BEFORE CREATION</span><h2>{employee.employee_name} · {employee.job_title}</h2><p>Nothing becomes a ticket until you click Start Onboarding.</p></div>
      <div class="review-count"><strong>{plan.filter(item => item.selected).length}</strong><span>tickets selected</span></div>
    </div>
    {#each departments as department}
      {@const departmentItems = plan.map((item, index) => ({ item, index })).filter(entry => entry.item.department === department)}
      {#if departmentItems.length}
        <div class="card-box plan-group">
          <h3>{department}<span>{departmentItems.length}</span></h3>
          {#each departmentItems as entry}
            <div class="plan-item" class:disabled={!entry.item.selected}>
              <input class="select-check" type="checkbox" checked={entry.item.selected} on:change={(event) => updatePlanItem(entry.index, 'selected', event.currentTarget.checked)} />
              <div class="plan-fields">
                <input class="title-input" value={entry.item.title} on:input={(event) => updatePlanItem(entry.index, 'title', event.currentTarget.value)} />
                <textarea rows="2" value={entry.item.description} on:input={(event) => updatePlanItem(entry.index, 'description', event.currentTarget.value)}></textarea>
                <div class="inline-fields">
                  <select value={entry.item.department} on:change={(event) => updatePlanItem(entry.index, 'department', event.currentTarget.value)}>{#each departments as option}<option value={option}>{option}</option>{/each}</select>
                  <select value={entry.item.category} on:change={(event) => updatePlanItem(entry.index, 'category', event.currentTarget.value)}>{#each categories[entry.item.department] as option}<option value={option}>{option}</option>{/each}</select>
                  <select value={entry.item.priority} on:change={(event) => updatePlanItem(entry.index, 'priority', event.currentTarget.value)}>{#each priorities as option}<option value={option}>{option}</option>{/each}</select>
                  <input type="date" value={entry.item.due_date} on:input={(event) => updatePlanItem(entry.index, 'due_date', event.currentTarget.value)} />
                </div>
              </div>
              <button class="icon-button danger" title="Remove suggestion" on:click={() => removePlanItem(entry.index)}><i class="ph-bold ph-trash"></i></button>
            </div>
          {/each}
        </div>
      {/if}
    {/each}
    <button class="add-custom" on:click={() => { customTicket = emptyTicket(); showCustomForm = true; }}><i class="ph-bold ph-plus-circle"></i> Add Custom Ticket</button>
    {#if showCustomForm}<div class="card-box"><h3>Custom onboarding ticket</h3><div class="custom-grid"><input bind:value={customTicket.title} placeholder="Ticket title" /><textarea bind:value={customTicket.description} placeholder="What needs to be completed?"></textarea><select bind:value={customTicket.department} on:change={() => customTicket.category = categories[customTicket.department].at(-1)}>{#each departments as option}<option value={option}>{option}</option>{/each}</select><select bind:value={customTicket.category}>{#each categories[customTicket.department] as option}<option value={option}>{option}</option>{/each}</select><select bind:value={customTicket.priority}>{#each priorities as option}<option value={option}>{option}</option>{/each}</select><input type="date" bind:value={customTicket.due_date} /></div><div class="footer-actions"><button class="btn-secondary" on:click={() => showCustomForm = false}>Cancel</button><button class="btn-primary" on:click={addCustomToPlan}>Add to Plan</button></div></div>{/if}
    <div class="sticky-actions"><button class="btn-secondary" on:click={() => mode = 'create'}>Back</button><button class="btn-primary" on:click={startOnboarding} disabled={working}>{working ? 'Creating tickets...' : 'Start Onboarding'} <i class="ph-bold ph-rocket-launch"></i></button></div>
  {:else if mode === 'detail' && selectedCase}
    <div class="detail-hero card-box">
      <div><span class="case-id">{selectedCase.id}</span><h2>{selectedCase.employee_name}</h2><p>{selectedCase.role} · {selectedCase.department} · Starts {selectedCase.start_date}</p><span class={`health-badge ${healthClass(selectedCase.health)}`}>{selectedCase.health}</span><span class="health-message">{selectedCase.health_message}</span></div>
      <div class="progress-ring"><strong>{selectedCase.progress_percentage}%</strong><span>{selectedCase.completed_tickets} of {selectedCase.total_tickets} complete</span></div>
    </div>
    <div class="department-grid">{#each Object.entries(selectedCase.department_progress || {}) as [department, progress]}<div class="department-card"><strong>{department}</strong><span>{progress.completed} / {progress.total} complete</span></div>{/each}</div>
    <div class="card-box">
      <div class="ticket-list-heading"><div><h3>Linked TicketGenie Tickets</h3><p>These are real tickets in their department queues.</p></div><button class="btn-primary small" on:click={() => { customTicket = emptyTicket(); showCustomForm = true; }}><i class="ph-bold ph-plus"></i> Add Ticket</button></div>
      {#if showCustomForm}<div class="inline-custom"><input bind:value={customTicket.title} placeholder="Ticket title" /><textarea bind:value={customTicket.description} placeholder="Description"></textarea><select bind:value={customTicket.department} on:change={() => customTicket.category = categories[customTicket.department].at(-1)}>{#each departments as option}<option value={option}>{option}</option>{/each}</select><select bind:value={customTicket.category}>{#each categories[customTicket.department] as option}<option value={option}>{option}</option>{/each}</select><select bind:value={customTicket.priority}>{#each priorities as option}<option value={option}>{option}</option>{/each}</select><input type="date" bind:value={customTicket.due_date} /><div><button class="btn-secondary" on:click={() => showCustomForm = false}>Cancel</button><button class="btn-primary" on:click={addTicketAfterStart} disabled={working}>Create Ticket</button></div></div>{/if}
      <div class="linked-tickets">{#each selectedCase.tickets as ticket}<button class:resolved={(ticket.status || '').toLowerCase() === 'resolved'} on:click={() => openTicket(ticket)}><span class="ticket-id">{ticket.id}</span><div><strong>{ticket.title}</strong><small>{ticket.department} · Due {ticket.due_date || 'Not set'}</small></div><span class="priority">{ticket.priority}</span><span class="status">{(ticket.status || '').toLowerCase() === 'resolved' ? '✓ Resolved' : ticket.status}</span><i class="ph-bold ph-arrow-square-out"></i></button>{/each}</div>
    </div>
  {/if}
</div>

<style>
  .onboarding-view{padding:28px;display:flex;flex-direction:column;gap:20px;height:100%;overflow-y:auto;box-sizing:border-box}.view-header{display:flex;justify-content:space-between;align-items:center;gap:20px}.view-title{font-size:1.55rem;margin:0;color:var(--text-main)}.view-subtitle,.section-heading p,.review-header p,.ticket-list-heading p{margin:5px 0 0;color:var(--text-muted);font-size:.86rem}.btn-primary,.btn-secondary{border-radius:9px;padding:10px 16px;font-weight:700;font-size:.82rem;cursor:pointer;display:inline-flex;align-items:center;gap:7px}.btn-primary{border:0;background:var(--primary);color:#fff}.btn-secondary{border:1px solid var(--border-color);background:#fff;color:var(--text-main)}button:disabled{opacity:.55;cursor:not-allowed}.card-box{background:#fff;border:1px solid var(--border-color);border-radius:14px;padding:22px;box-shadow:var(--shadow-sm)}.error-banner{padding:12px 15px;border-radius:9px;background:#fef2f2;color:#b91c1c;border:1px solid #fecaca}.summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.summary-card{background:#fff;border:1px solid var(--border-color);border-left:4px solid #6366f1;border-radius:12px;padding:18px;display:flex;justify-content:space-between;align-items:center}.summary-card span{color:var(--text-muted);font-size:.82rem}.summary-card strong{font-size:1.6rem}.summary-card.risk{border-left-color:#f59e0b}.summary-card.complete{border-left-color:#10b981}.case-list{display:flex;flex-direction:column}.case-row{display:grid;grid-template-columns:2fr .8fr 1.4fr auto auto;align-items:center;gap:22px;width:100%;padding:17px 10px;border:0;border-bottom:1px solid var(--border-color);background:#fff;text-align:left;cursor:pointer;color:var(--text-main)}.case-row:hover{background:#fafafa}.case-row div:first-child{display:flex;flex-direction:column;gap:3px}.case-row small{color:var(--text-muted)}.case-id,.ticket-id{font-family:monospace;color:var(--primary);font-weight:800;font-size:.76rem}.progress-block>div:first-child{display:flex;justify-content:space-between;font-size:.75rem}.progress-track{height:6px;background:#e5e7eb;border-radius:8px;margin-top:7px;overflow:hidden}.progress-track span{display:block;height:100%;background:#6366f1;border-radius:8px}.health-badge{display:inline-flex;width:max-content;padding:5px 9px;border-radius:20px;font-size:.72rem;font-weight:800;background:#dbeafe;color:#1d4ed8}.health-badge.at-risk{background:#fef3c7;color:#b45309}.health-badge.blocked{background:#fee2e2;color:#b91c1c}.health-badge.complete{background:#d1fae5;color:#047857}.empty-state{padding:55px;display:flex;flex-direction:column;align-items:center;gap:7px;color:var(--text-muted)}.section-heading{display:flex;gap:13px;align-items:flex-start;margin-bottom:22px}.section-heading>span{width:30px;height:30px;border-radius:50%;background:#ede9fe;color:#6d28d9;display:grid;place-items:center;font-weight:800}.section-heading h2,.review-header h2,.detail-hero h2{margin:0}.form-grid,.custom-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:17px}.form-grid label{display:flex;flex-direction:column;gap:7px;font-size:.78rem;font-weight:700}.form-grid input,.plan-fields input,.plan-fields textarea,.plan-fields select,.custom-grid input,.custom-grid textarea,.custom-grid select,.inline-custom input,.inline-custom textarea,.inline-custom select{border:1px solid #d1d5db;border-radius:8px;padding:10px;font:inherit;color:var(--text-main);background:#fff}.footer-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:20px}.review-header,.detail-hero{display:flex;justify-content:space-between;align-items:center}.eyebrow{font-size:.68rem;font-weight:800;color:#7c3aed}.review-count{text-align:center}.review-count strong{display:block;font-size:1.8rem}.review-count span{font-size:.75rem;color:var(--text-muted)}.plan-group h3{display:flex;align-items:center;gap:8px;margin-top:0}.plan-group h3 span{background:#ede9fe;color:#6d28d9;border-radius:12px;padding:2px 8px;font-size:.7rem}.plan-item{display:grid;grid-template-columns:auto 1fr auto;gap:13px;padding:16px 0;border-top:1px solid var(--border-color)}.plan-item.disabled{opacity:.5}.select-check{width:18px;height:18px;margin-top:11px}.plan-fields{display:flex;flex-direction:column;gap:8px}.title-input{font-weight:800}.inline-fields{display:grid;grid-template-columns:1.1fr 1.2fr .7fr .8fr;gap:8px}.icon-button{width:35px;height:35px;border-radius:8px;border:1px solid var(--border-color);background:#fff;cursor:pointer}.icon-button.danger{color:#dc2626}.add-custom{padding:18px;border:2px dashed #c4b5fd;border-radius:12px;background:#faf5ff;color:#6d28d9;font-weight:800;cursor:pointer}.custom-grid textarea{grid-column:span 2;min-height:75px}.sticky-actions{position:sticky;bottom:-28px;z-index:3;background:#fff;border-top:1px solid var(--border-color);padding:15px 20px;display:flex;justify-content:flex-end;gap:10px;box-shadow:0 -8px 18px rgba(0,0,0,.06)}.detail-hero>div:first-child{display:flex;flex-direction:column;gap:7px}.health-message{font-size:.8rem;color:var(--text-muted)}.progress-ring{width:150px;height:150px;border:12px solid #ddd6fe;border-top-color:#7c3aed;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.progress-ring strong{font-size:1.8rem}.progress-ring span{font-size:.7rem;color:var(--text-muted)}.department-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.department-card{background:#fff;border:1px solid var(--border-color);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:5px}.department-card span{font-size:.75rem;color:var(--text-muted)}.ticket-list-heading{display:flex;justify-content:space-between;align-items:center}.ticket-list-heading h3{margin:0}.btn-primary.small{padding:8px 11px}.linked-tickets{margin-top:16px}.linked-tickets>button{width:100%;display:grid;grid-template-columns:.7fr 2fr .7fr .7fr auto;gap:15px;align-items:center;padding:14px 8px;border:0;border-top:1px solid var(--border-color);background:#fff;text-align:left;cursor:pointer;color:var(--text-main)}.linked-tickets>button:hover{background:#fafafa}.linked-tickets div{display:flex;flex-direction:column;gap:3px}.linked-tickets small{color:var(--text-muted)}.priority,.status{font-size:.74rem;font-weight:700}.inline-custom{margin-top:15px;padding:15px;border-radius:10px;background:#f8fafc;display:grid;grid-template-columns:1fr 1fr;gap:9px}.inline-custom textarea{grid-column:span 2}.inline-custom>div{grid-column:span 2;display:flex;justify-content:flex-end;gap:8px}@media(max-width:850px){.summary-grid,.form-grid{grid-template-columns:1fr}.case-row{grid-template-columns:1fr}.inline-fields{grid-template-columns:1fr 1fr}.detail-hero{align-items:flex-start}.progress-ring{width:110px;height:110px}.linked-tickets>button{grid-template-columns:1fr}.custom-grid{grid-template-columns:1fr}.custom-grid textarea{grid-column:span 1}}
  .case-row.resolved,
  .linked-tickets > button.resolved { background:#ecfdf5; border-color:#a7f3d0; box-shadow:inset 4px 0 #10b981; }
  .case-row.resolved:hover,
  .linked-tickets > button.resolved:hover { background:#d1fae5; }
  .linked-tickets > button.resolved .status { color:#047857; font-weight:800; }
</style>
