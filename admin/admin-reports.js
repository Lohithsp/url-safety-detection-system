document.addEventListener('DOMContentLoaded', () => {
  const btnDaily = document.getElementById('btn-daily-report');
  const btnWeekly = document.getElementById('btn-weekly-report');
  const btnMonthly = document.getElementById('btn-monthly-report');
  const btnCustomToggle = document.getElementById('btn-custom-report-toggle');
  const customDateContainer = document.getElementById('custom-date-container');
  const startDateInput = document.getElementById('start-date');
  const endDateInput = document.getElementById('end-date');
  const btnDownloadCustom = document.getElementById('btn-download-custom');

  const emailInput = document.getElementById('report-email');

  // Fetch session details to pre-fill admin email
  async function loadAdminEmail() {
    try {
      const res = await fetch('../php/check_session.php');
      const data = await res.json();
      if (data.success && data.user && data.user.email) {
        if (emailInput) {
          emailInput.value = data.user.email;
        }
      }
    } catch (err) {
      console.error('Failed to load session details:', err);
    }
  }
  loadAdminEmail();

  // Trigger report download directly by setting window.location
  function downloadReport(type, params = {}) {
    let url = `../php/generate_report.php?type=${type}`;
    if (emailInput && emailInput.value.trim()) {
      url += `&email=${encodeURIComponent(emailInput.value.trim())}`;
    }
    for (const key in params) {
      url += `&${key}=${encodeURIComponent(params[key])}`;
    }
    window.location.href = url;
  }

  if (btnDaily) {
    btnDaily.addEventListener('click', () => {
      downloadReport('daily');
    });
  }

  if (btnWeekly) {
    btnWeekly.addEventListener('click', () => {
      downloadReport('weekly');
    });
  }

  if (btnMonthly) {
    btnMonthly.addEventListener('click', () => {
      downloadReport('monthly');
    });
  }

  if (btnCustomToggle) {
    btnCustomToggle.addEventListener('click', () => {
      const isHidden = customDateContainer.style.display === 'none' || !customDateContainer.style.display;
      customDateContainer.style.display = isHidden ? 'block' : 'none';
      if (isHidden) {
        // Default start date to 7 days ago and end date to today
        const today = new Date();
        const past = new Date();
        past.setDate(today.getDate() - 7);

        const formatDate = (d) => d.toISOString().split('T')[0];
        startDateInput.value = formatDate(past);
        endDateInput.value = formatDate(today);
      }
    });
  }

  if (btnDownloadCustom) {
    btnDownloadCustom.addEventListener('click', () => {
      const start = startDateInput.value;
      const end = endDateInput.value;

      if (!start || !end) {
        alert('Please select both start and end dates.');
        return;
      }

      if (new Date(start) > new Date(end)) {
        alert('Start date cannot be after end date.');
        return;
      }

      downloadReport('custom', { start_date: start, end_date: end });
    });
  }
});
