// Profile dropdown for topbar profile chip (Profile / Settings / Logout)
document.addEventListener('DOMContentLoaded', function () {
  const profileButtons = document.querySelectorAll('.topbar .topbar-actions .profile-chip');
  profileButtons.forEach(btn => {
    if (btn.dataset.dropdownAttached) return;
    btn.dataset.dropdownAttached = '1';

    const dropdown = document.createElement('div');
    dropdown.className = 'profile-dropdown';
    dropdown.innerHTML = `
      <a href="settings.html">Profile</a>
      <a href="settings.html">Settings</a>
      <a href="#" data-action="logout">Logout</a>
    `;
    document.body.appendChild(dropdown);

    function positionDropdown() {
      const rect = btn.getBoundingClientRect();
      const right = window.innerWidth - rect.right;
      dropdown.style.top = (rect.bottom + 8) + 'px';
      dropdown.style.right = right + 'px';
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = btn.classList.toggle('open');
      if (isOpen) {
        dropdown.style.display = 'flex';
        positionDropdown();
      } else {
        dropdown.style.display = 'none';
      }
    });

    window.addEventListener('resize', function () { if (btn.classList.contains('open')) positionDropdown(); });
    window.addEventListener('scroll', function () { if (btn.classList.contains('open')) positionDropdown(); }, true);

    dropdown.addEventListener('click', function (e) {
      e.stopPropagation();
      const target = e.target.closest('a');
      if (!target) return;
      const action = target.dataset.action;
      if (action === 'logout') {
        e.preventDefault();
        fetch('../php/logout.php', { method: 'GET', credentials: 'include' })
          .then(res => res.json().catch(() => ({ success: false })))
          .then(data => {
            const redirect = (data && data.redirect) ? data.redirect : '../index.html';
            window.location.href = redirect;
          })
          .catch(() => { window.location.href = '../index.html'; });
        return;
      }
      btn.classList.remove('open');
      dropdown.style.display = 'none';
    });
  });

  // global outside click to close all
  document.addEventListener('click', function () {
    document.querySelectorAll('.topbar .topbar-actions .profile-chip.open').forEach(openBtn => openBtn.classList.remove('open'));
    document.querySelectorAll('.profile-dropdown').forEach(dd => dd.style.display = 'none');
  });
  // close with Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.topbar .topbar-actions .profile-chip.open').forEach(openBtn => openBtn.classList.remove('open'));
      document.querySelectorAll('.profile-dropdown').forEach(dd => dd.style.display = 'none');
    }
  });
});
const scanForm = document.getElementById("scanForm");
const urlInput = document.getElementById("urlInput");
let statusPill = document.getElementById("statusPill");
let resultCard = document.getElementById("resultCard");
let resultHeading = resultCard?.querySelector("h3");
let resultText = document.getElementById("resultText");
let featureGrid = document.getElementById("featureGrid");
const recentLists = Array.from(document.querySelectorAll('.recent-list'));

let localHistoryCache = [];

async function loadHistoryFromServer() {
  try {
    const response = await fetch('../php/history.php');
    if (!response.ok) {
      throw new Error('Failed to load history');
    }
    const data = await response.json();
    if (data.success && Array.isArray(data.scans)) {
      localHistoryCache = data.scans.map(scan => ({
        url: scan.url,
        displayUrl: scan.url,
        status: scan.prediction,
        pillClass: pillClassForStatus(scan.prediction),
        confidence: scan.confidence,
        riskLevel: scan.risk_level,
        explanation: scan.explanation || '',
        time: scan.scan_time
      }));
    }
  } catch (error) {
    console.error('Error fetching scan history:', error);
    try {
      const raw = localStorage.getItem('urlguard-history');
      localHistoryCache = raw ? JSON.parse(raw) : [];
    } catch (e) {
      localHistoryCache = [];
    }
  }
}

function renderHistory() {
  const items = localHistoryCache;
  recentLists.forEach(container => {
    container.innerHTML = '';
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'recent-empty';
      empty.textContent = 'No history yet — scan a URL to populate recent scans.';
      container.appendChild(empty);
      return;
    }

    items.forEach(entry => {
      const art = document.createElement('article');
      art.className = 'recent-item';
      const left = document.createElement('div');
      const strong = document.createElement('strong');
      strong.textContent = entry.displayUrl || entry.url;
      const p = document.createElement('p');
      
      let whenText = '';
      if (entry.time) {
        const parsedDate = new Date(entry.time);
        if (!isNaN(parsedDate.getTime())) {
          whenText = parsedDate.toLocaleString();
        } else {
          whenText = String(entry.time);
        }
      }
      p.textContent = whenText;
      left.appendChild(strong);
      left.appendChild(p);

      const pill = document.createElement('span');
      pill.className = 'status-pill ' + (entry.pillClass || (entry.status === 'Safe' ? 'status-safe' : (entry.status === 'Malicious' ? 'status-malicious' : 'status-suspicious')));
      pill.textContent = entry.status;

      art.appendChild(left);
      art.appendChild(pill);
      container.appendChild(art);
    });
  });
}

async function initHistory() {
  await loadHistoryFromServer();
  renderHistory();
}

// Load and render history from server
initHistory();

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function pillClassForStatus(status) {
  if (status === 'Malicious') return 'status-malicious';
  if (status === 'Suspicious') return 'status-suspicious';
  return 'status-safe';
}

function buildMlFeatures(result) {
  const reasons = Array.isArray(result.reasons) ? result.reasons : [];
  const features = [
    ['Confidence Score', `${result.confidence ?? 'N/A'}%`],
    ['Risk Level', result.risk_level || 'Low'],
  ];

  reasons.slice(0, 4).forEach((reason, index) => {
    features.push([`Reason ${index + 1}`, reason]);
  });

  return features;
}

function renderScanResult(result) {
  const status = result.prediction || result.status_label || 'Safe';
  const pillClass = result.pillClass || pillClassForStatus(status);
  const features = buildMlFeatures(result);
  const explanation = result.explanation || 'The trained ML model completed the scan.';

  if (!resultCard) {
    const hero = document.querySelector('.hero-card');
    const sec = document.createElement('section');
    sec.className = 'result-card card';
    sec.id = 'resultCard';
    sec.innerHTML = `
      <div class="result-header">
        <div>
          <p class="eyebrow">Latest ML Scan Result</p>
          <h3>${escapeHtml(status)}</h3>
        </div>
        <span class="status-pill ${escapeHtml(pillClass)}" id="statusPill">${escapeHtml(status)}</span>
      </div>
      <p class="result-text" id="resultText">${escapeHtml(explanation)}</p>
      <div class="feature-grid" id="featureGrid">
        ${features.map(([l, v]) => `<article class="feature-item"><span class="feature-label">${escapeHtml(l)}</span><strong>${escapeHtml(v)}</strong></article>`).join('')}
      </div>
    `;
    if (hero && hero.parentNode) {
      hero.parentNode.insertBefore(sec, hero.nextSibling);
    } else {
      document.body.appendChild(sec);
    }

    resultCard = document.getElementById('resultCard');
    statusPill = document.getElementById('statusPill');
    resultHeading = resultCard.querySelector('h3');
    resultText = document.getElementById('resultText');
    featureGrid = document.getElementById('featureGrid');
  } else {
    resultCard.style.display = '';
    statusPill.textContent = status;
    statusPill.className = `status-pill ${pillClass}`;
    resultHeading.textContent = status;
    resultText.textContent = explanation;
    featureGrid.innerHTML = features
      .map(([label, value]) => `
        <article class="feature-item">
          <span class="feature-label">${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </article>
      `)
      .join('');
  }

  return { status, pillClass };
}

if (scanForm && urlInput) {
  scanForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const rawInput = urlInput.value.trim();
    let submittedUrl = rawInput;

    if (!submittedUrl) {
      urlInput.focus();
      return;
    }

    // Normalize URLs: allow users to omit protocol (e.g. "www.google.com")
    if (!/^https?:\/\//i.test(submittedUrl)) {
      submittedUrl = 'https://' + submittedUrl;
    }

    const submitButton = scanForm.querySelector('button[type="submit"]');
    const originalButtonText = submitButton?.textContent;
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = 'Scanning with ML...';
    }

    try {
      const response = await fetch('../php/scan.php', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: submittedUrl }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Unable to scan this URL.');
      }

      const rendered = renderScanResult(data);
      await loadHistoryFromServer();
      renderHistory();
      resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      renderScanResult({
        prediction: 'Scan Error',
        pillClass: 'status-suspicious',
        risk_level: 'Unavailable',
        confidence: 'N/A',
        explanation: error.message || 'The ML scan endpoint did not respond.',
        reasons: ['Check that the Flask server is running', 'Confirm the trained model exists in models/best_url_model.joblib'],
      });
      resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText || 'Check URL Safety';
      }
    }
  });
}
