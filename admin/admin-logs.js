document.addEventListener('DOMContentLoaded', () => {
  const tbody = document.querySelector('tbody');
  const searchInput = document.getElementById('adminSearch');
  let logsCache = [];

  function formatTime(timeStr) {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    return isNaN(date.getTime()) ? timeStr : date.toLocaleString();
  }

  function getStatusClass(status) {
    const s = String(status || '').toLowerCase();
    if (s === 'success' || s === 'approved' || s === 'safe') return 'status-safe';
    if (s === 'failed' || s === 'rejected' || s === 'malicious') return 'status-malicious';
    return 'status-suspicious';
  }

  function renderLogs(logs) {
    tbody.innerHTML = '';
    if (logs.length === 0) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="4" class="empty-state-cell" style="text-align: center; padding: 40px;">No matching activity logs available</td>`;
      tbody.appendChild(tr);
      return;
    }

    logs.forEach(log => {
      const tr = document.createElement('tr');
      
      const tdTime = document.createElement('td');
      tdTime.textContent = formatTime(log.timestamp);
      
      const tdEvent = document.createElement('td');
      tdEvent.textContent = log.event;
      tdEvent.style.wordBreak = 'break-all';
      
      const tdUser = document.createElement('td');
      tdUser.textContent = log.user;
      
      const tdStatus = document.createElement('td');
      const spanStatus = document.createElement('span');
      spanStatus.className = 'status-pill ' + getStatusClass(log.status);
      spanStatus.textContent = log.status;
      tdStatus.appendChild(spanStatus);
      
      tr.appendChild(tdTime);
      tr.appendChild(tdEvent);
      tr.appendChild(tdUser);
      tr.appendChild(tdStatus);
      tbody.appendChild(tr);
    });
  }

  async function loadLogs() {
    try {
      const res = await fetch('../php/system_logs.php');
      if (!res.ok) throw new Error('Failed to load logs');
      const data = await res.json();
      if (data.success && Array.isArray(data.logs)) {
        logsCache = data.logs;
        renderLogs(logsCache);
      } else {
        console.error('Failed to load logs:', data.message);
      }
    } catch (err) {
      console.error(err);
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--malicious); padding: 40px;">Error loading logs from server</td></tr>`;
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase().trim();
      if (!query) {
        renderLogs(logsCache);
        return;
      }
      const filtered = logsCache.filter(log => 
        String(log.timestamp).toLowerCase().includes(query) ||
        String(log.event).toLowerCase().includes(query) ||
        String(log.user).toLowerCase().includes(query) ||
        String(log.status).toLowerCase().includes(query)
      );
      renderLogs(filtered);
    });
  }

  loadLogs();
});
