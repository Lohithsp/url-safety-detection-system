document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('bulk-scan-form');
  const textarea = document.getElementById('bulk-scan-urls');
  const submitBtn = document.getElementById('bulk-scan-btn');
  const resultsCard = document.getElementById('bulk-results-card');
  const resultsBody = document.getElementById('bulk-results-body');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = textarea.value.trim();
    if (!text) {
      alert('Please enter at least one URL');
      return;
    }

    const urls = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    if (urls.length === 0) return;

    submitBtn.disabled = true;
    submitBtn.textContent = 'Scanning...';
    resultsCard.style.display = 'block';
    resultsBody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px;">Scanning URLs... Please wait.</td></tr>`;

    const results = [];
    for (const url of urls) {
      try {
        const response = await fetch('../php/scan.php', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ url: url })
        });
        const data = await response.json();
        if (data.success) {
          results.push({
            url: url,
            prediction: data.prediction,
            confidence: data.confidence,
            risk_level: data.risk_level,
            explanation: data.explanation || '-'
          });
        } else {
          results.push({
            url: url,
            prediction: 'Error',
            confidence: null,
            risk_level: 'High',
            explanation: data.message || 'Error occurred during scan'
          });
        }
      } catch (err) {
        results.push({
          url: url,
          prediction: 'Error',
          confidence: null,
          risk_level: 'High',
          explanation: err.message || 'Connection failed'
        });
      }
    }

    // Render results
    resultsBody.innerHTML = '';
    results.forEach(res => {
      const tr = document.createElement('tr');
      
      const tdUrl = document.createElement('td');
      tdUrl.textContent = res.url;
      tdUrl.style.wordBreak = 'break-all';
      
      const tdVerdict = document.createElement('td');
      const spanVerdict = document.createElement('span');
      const isSafe = String(res.prediction).toLowerCase() === 'safe';
      spanVerdict.className = 'status-pill ' + (isSafe ? 'status-safe' : 'status-malicious');
      spanVerdict.textContent = res.prediction;
      tdVerdict.appendChild(spanVerdict);
      
      const tdConfidence = document.createElement('td');
      tdConfidence.textContent = res.confidence != null ? `${Number(res.confidence).toFixed(1)}%` : 'N/A';
      
      const tdRisk = document.createElement('td');
      const spanRisk = document.createElement('span');
      let riskClass = 'status-suspicious';
      if (res.risk_level.toLowerCase() === 'low') riskClass = 'status-safe';
      if (res.risk_level.toLowerCase() === 'high') riskClass = 'status-malicious';
      spanRisk.className = 'status-pill ' + riskClass;
      spanRisk.textContent = res.risk_level;
      tdRisk.appendChild(spanRisk);
      
      const tdExpl = document.createElement('td');
      tdExpl.textContent = res.explanation;
      
      tr.appendChild(tdUrl);
      tr.appendChild(tdVerdict);
      tr.appendChild(tdConfidence);
      tr.appendChild(tdRisk);
      tr.appendChild(tdExpl);
      
      resultsBody.appendChild(tr);
    });

    submitBtn.disabled = false;
    submitBtn.textContent = 'Scan URLs';
  });
});
