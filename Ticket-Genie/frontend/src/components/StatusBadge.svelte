<script>
  export let status = 'Open';
  export let type = 'status'; // 'status' or 'priority'

  $: normalized = (status || '').toLowerCase();
</script>

{#if type === 'status'}
  <span class="badge status-{normalized}">
    <span class="dot"></span>
    {status}
  </span>
{:else}
  <span class="badge priority-{normalized}">
    <i class="ph-bold {normalized === 'high' || normalized === 'urgent' ? 'ph-warning' : 'ph-circle'}"></i>
    {status}
  </span>
{/if}

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: capitalize;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  /* Status Colors */
  .status-open {
    background: #eff6ff;
    color: #2563eb;
    border: 1px solid #bfdbfe;
  }
  .status-open .dot { background: #2563eb; }

  .status-in_progress, .status-in-progress, .status-progress {
    background: #fffbeb;
    color: #b45309;
    border: 1px solid #fef08a;
  }
  .status-in_progress .dot, .status-in-progress .dot { background: #d97706; }

  .status-resolved, .status-closed {
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #a7f3d0;
  }
  .status-resolved .dot, .status-closed .dot { background: #10b981; }

  /* Priority Colors */
  .priority-high, .priority-urgent {
    background: #fef2f2;
    color: #dc2626;
    border: 1px solid #fecaca;
  }

  .priority-medium {
    background: #fffbeb;
    color: #d97706;
    border: 1px solid #fde68a;
  }

  .priority-low {
    background: #f0fdf4;
    color: #16a34a;
    border: 1px solid #bbf7d0;
  }
</style>
