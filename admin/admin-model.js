(function() {
  async function loadModelMetrics() {
    try {
      const response = await fetch('../php/model_performance.php');
      if (!response.ok) {
        throw new Error('Failed to load model metrics');
      }
      
      const data = await response.json();
      if (data.success) {
        const bestModelName = data.best_model || 'XGBoost';
        const bestMetrics = data.metrics || {};
        const allModels = data.all_models || [];
        const lastUpdated = data.last_updated || 'N/A';

        // Update ML Model Information
        const typeEl = document.getElementById('model-type');
        if (typeEl) {
          typeEl.textContent = `${bestModelName} Classifier`;
        }

        const accEl = document.getElementById('model-accuracy');
        const bestAcc = bestMetrics.accuracy !== undefined ? bestMetrics.accuracy : (bestMetrics.accuracy_score || 0);
        if (accEl) {
          accEl.textContent = (bestAcc * 100).toFixed(2) + '%';
        }

        const updatedEl = document.getElementById('model-updated');
        if (updatedEl) {
          updatedEl.textContent = lastUpdated;
        }

        // Populate all models table
        const tbody = document.getElementById('all-models-tbody');
        if (tbody) {
          tbody.innerHTML = '';
          if (allModels.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state-cell">No model data found.</td></tr>';
          } else {
            // Sort models by accuracy descending
            allModels.sort((a, b) => {
              const accA = a.accuracy !== undefined ? a.accuracy : (a.accuracy_score || 0);
              const accB = b.accuracy !== undefined ? b.accuracy : (b.accuracy_score || 0);
              return accB - accA;
            });

            allModels.forEach(m => {
              const tr = document.createElement('tr');
              
              const tdModel = document.createElement('td');
              tdModel.innerHTML = `<strong>${m.model}</strong> ${m.model === bestModelName ? '<span style="background: var(--safe-soft); color: var(--safe); font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; margin-left: 8px;">Active</span>' : ''}`;
              
              const tdAcc = document.createElement('td');
              const accVal = m.accuracy !== undefined ? m.accuracy : (m.accuracy_score || 0);
              tdAcc.textContent = (accVal * 100).toFixed(2) + '%';
              
              const tdPrec = document.createElement('td');
              const precVal = m.precision !== undefined ? m.precision : (m.precision_score || 0);
              tdPrec.textContent = (precVal * 100).toFixed(2) + '%';
              
              const tdRec = document.createElement('td');
              const recVal = m.recall !== undefined ? m.recall : (m.recall_score || 0);
              tdRec.textContent = (recVal * 100).toFixed(2) + '%';
              
              const tdF1 = document.createElement('td');
              const f1Val = m.f1 !== undefined ? m.f1 : (m.f1_score || 0);
              tdF1.textContent = (f1Val * 100).toFixed(2) + '%';
              
              const tdAuc = document.createElement('td');
              const aucVal = m.roc_auc !== undefined ? m.roc_auc : (m.auc_roc || 0);
              tdAuc.textContent = (aucVal * 100).toFixed(2) + '%';

              tr.appendChild(tdModel);
              tr.appendChild(tdAcc);
              tr.appendChild(tdPrec);
              tr.appendChild(tdRec);
              tr.appendChild(tdF1);
              tr.appendChild(tdAuc);
              tbody.appendChild(tr);
            });
          }
        }
      }
    } catch (error) {
      console.error('Error fetching model performance overview:', error);
      const tbody = document.getElementById('all-models-tbody');
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state-cell" style="color: var(--malicious);">Error loading model metrics.</td></tr>';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', loadModelMetrics);
  if (document.readyState === 'interactive' || document.readyState === 'complete') {
    loadModelMetrics();
  }
})();
