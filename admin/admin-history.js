document.addEventListener('DOMContentLoaded', () => {
  const tbody = document.getElementById('history-table-body');
  const searchInput = document.getElementById('adminSearch');
  let historyCache = [];

  function formatTime(timeStr) {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    return isNaN(date.getTime()) ? timeStr : date.toLocaleString();
  }

  function getStatusClass(prediction) {
    const p = String(prediction || '').toLowerCase();
    if (p === 'safe') return 'status-safe';
    if (p === 'malicious') return 'status-malicious';
    return 'status-suspicious';
  }

  function getRiskClass(risk) {
    const r = String(risk || '').toLowerCase();
    if (r === 'low') return 'status-safe';
    if (r === 'high') return 'status-malicious';
    return 'status-suspicious';
  }

  function renderHistory(scans) {
    tbody.innerHTML = '';
    if (scans.length === 0) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="9" class="empty-state-cell" style="text-align: center; padding: 40px;">No matching scan history available</td>`;
      tbody.appendChild(tr);
      return;
    }

    scans.forEach(scan => {
      const tr = document.createElement('tr');
      
      const tdUserId = document.createElement('td');
      tdUserId.textContent = scan.user_id;
      
      const tdName = document.createElement('td');
      tdName.textContent = scan.user_name;
      
      const tdEmail = document.createElement('td');
      tdEmail.textContent = scan.user_email;
      tdEmail.style.wordBreak = 'break-all';

      const tdRole = document.createElement('td');
      tdRole.textContent = scan.user_role || 'Guest';
      
      const tdUrl = document.createElement('td');
      tdUrl.textContent = scan.url;
      tdUrl.style.wordBreak = 'break-all';
      
      const tdResult = document.createElement('td');
      const spanResult = document.createElement('span');
      spanResult.className = 'status-pill ' + getStatusClass(scan.prediction);
      spanResult.textContent = scan.prediction;
      tdResult.appendChild(spanResult);
      
      const tdConfidence = document.createElement('td');
      tdConfidence.textContent = (scan.confidence != null) ? `${Number(scan.confidence).toFixed(1)}%` : 'N/A';
      
      const tdRisk = document.createElement('td');
      const spanRisk = document.createElement('span');
      spanRisk.className = 'status-pill ' + getRiskClass(scan.risk_level);
      spanRisk.textContent = scan.risk_level || 'N/A';
      tdRisk.appendChild(spanRisk);
      
      const tdTime = document.createElement('td');
      tdTime.textContent = formatTime(scan.scan_time);
      
      tr.appendChild(tdUserId);
      tr.appendChild(tdName);
      tr.appendChild(tdEmail);
      tr.appendChild(tdRole);
      tr.appendChild(tdUrl);
      tr.appendChild(tdResult);
      tr.appendChild(tdConfidence);
      tr.appendChild(tdRisk);
      tr.appendChild(tdTime);
      tbody.appendChild(tr);
    });
  }

  async function loadHistory() {
    try {
      const res = await fetch('../php/history.php');
      if (!res.ok) throw new Error('Failed to load history');
      const data = await res.json();
      if (data.success && Array.isArray(data.scans)) {
        historyCache = data.scans;
        renderHistory(historyCache);
      } else {
        console.error('Failed to load history:', data.message);
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--malicious); padding: 40px;">Failed to load history: ${data.message || 'Unknown error'}</td></tr>`;
      }
    } catch (err) {
      console.error(err);
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--malicious); padding: 40px;">Error loading scan history from server</td></tr>`;
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase().trim();
      if (!query) {
        renderHistory(historyCache);
        return;
      }
      const filtered = historyCache.filter(scan => 
        String(scan.user_id).toLowerCase().includes(query) ||
        String(scan.user_name).toLowerCase().includes(query) ||
        String(scan.user_email).toLowerCase().includes(query) ||
        String(scan.user_role).toLowerCase().includes(query) ||
        String(scan.url).toLowerCase().includes(query) ||
        String(scan.prediction).toLowerCase().includes(query) ||
        String(scan.risk_level).toLowerCase().includes(query) ||
        String(scan.scan_time).toLowerCase().includes(query)
      );
      renderHistory(filtered);
    });
  }

  loadHistory();
});
