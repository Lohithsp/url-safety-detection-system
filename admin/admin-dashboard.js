document.addEventListener('DOMContentLoaded', function () {
  const checkInterval = 30000; // Auto-refresh stats every 30 seconds

  // Helper to escape HTML tags to avoid XSS
  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Format datetime strings cleanly
  function formatDate(dateString) {
    if (!dateString) return 'Never';
    // Normalize SQL datetime string YYYY-MM-DD HH:MM:SS to ISO standard
    let ds = String(dateString);
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(ds)) {
      ds = ds.replace(' ', 'T');
    }
    const d = new Date(ds);
    if (isNaN(d.getTime())) {
      return String(dateString);
    }
    return d.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }

  // Get CSS class based on status/prediction
  function getPillClass(prediction, riskLevel) {
    if (prediction === 'Safe') return 'status-safe';
    if (prediction === 'Malicious') {
      if (riskLevel === 'High') return 'status-malicious';
      return 'status-suspicious';
    }
    return 'status-safe';
  }

  // Verify session and check if admin role exists
  async function checkAdminSession() {
    try {
      const response = await fetch('../php/check_session.php');
      const data = await response.json();
      if (!data.logged_in || data.user.role !== 'admin') {
        window.location.href = '../index.html';
        return false;
      }
      return true;
    } catch (err) {
      console.error('Session validation error:', err);
      window.location.href = '../index.html';
      return false;
    }
  }

  // Fetch admin dashboard stats and update UI elements
  async function fetchDashboardStats() {
    try {
      const response = await fetch('../php/admin_stats.php');
      if (!response.ok) {
        if (response.status === 403) {
          window.location.href = '../index.html';
          return;
        }
        throw new Error(`Server returned status code: ${response.status}`);
      }

      const data = await response.json();
      if (data.success) {
        // Update stats counters
        const stats = data.stats || { total: 0, safe: 0, malicious: 0, suspicious: 0 };
        
        // Total scans
        const totalVal = document.getElementById('stat-total-scans');
        const totalNote = document.getElementById('note-total-scans');
        if (totalVal) totalVal.textContent = stats.total;
        if (totalNote) totalNote.textContent = stats.total > 0 ? `${stats.total} total scans recorded` : 'No scan data yet';

        // Safe scans
        const safeVal = document.getElementById('stat-safe-urls');
        const safeNote = document.getElementById('note-safe-urls');
        if (safeVal) safeVal.textContent = stats.safe;
        if (safeNote) safeNote.textContent = stats.total > 0 ? `${Math.round((stats.safe / stats.total) * 100) || 0}% safe rate` : 'Awaiting results';

        // Malicious scans
        const malVal = document.getElementById('stat-malicious-urls');
        const malNote = document.getElementById('note-malicious-urls');
        if (malVal) malVal.textContent = stats.malicious;
        if (malNote) malNote.textContent = stats.total > 0 ? `${Math.round((stats.malicious / stats.total) * 100) || 0}% malicious rate` : 'Awaiting results';

        // Suspicious scans
        const susVal = document.getElementById('stat-suspicious-urls');
        const susNote = document.getElementById('note-suspicious-urls');
        if (susVal) susVal.textContent = stats.suspicious;
        if (susNote) susNote.textContent = stats.total > 0 ? `${Math.round((stats.suspicious / stats.total) * 100) || 0}% suspicious rate` : 'Awaiting results';

        // Render recent scans table
        const tbody = document.getElementById('recent-scans-tbody');
        if (tbody) {
          const recent = data.recent_scans || [];
          if (recent.length === 0) {
            tbody.innerHTML = `
              <tr>
                <td colspan="4" class="empty-state-cell" style="text-align: center; padding: 40px;">
                  No URL scans have been recorded yet. Results will appear here once the system starts processing requests.
                </td>
              </tr>
            `;
          } else {
            tbody.innerHTML = recent.map(scan => {
              const pillClass = getPillClass(scan.prediction, scan.risk_level);
              return `
                <tr>
                  <td><strong class="url-text" title="${escapeHtml(scan.url)}">${escapeHtml(scan.url)}</strong></td>
                  <td><span class="status-pill ${pillClass}">${escapeHtml(scan.prediction)}</span></td>
                  <td>${escapeHtml(formatDate(scan.scan_time))}</td>
                  <td><a href="history.html" class="action-btn approve-btn" style="text-decoration: none;">View Details</a></td>
                </tr>
              `;
            }).join('');
          }
        }
      }
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
    }
  }

  // Init
  async function init() {
    const isLogged = await checkAdminSession();
    if (!isLogged) return;

    await fetchDashboardStats();

    // Auto-refresh loop
    setInterval(fetchDashboardStats, checkInterval);
  }

  init();
});
