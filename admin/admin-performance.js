(function() {
  async function loadPerformanceMetrics() {
    try {
      const response = await fetch('../php/model_performance.php');
      if (!response.ok) {
        throw new Error('Failed to load performance metrics');
      }
      
      const data = await response.json();
      if (data.success && data.metrics) {
        const metrics = data.metrics;
        const modelName = data.best_model || 'XGBoost';

        // Precision
        const precisionEl = document.getElementById('perf-precision');
        const precVal = metrics.precision || metrics.precision_score;
        if (precisionEl && precVal !== undefined) {
          precisionEl.textContent = (precVal * 100).toFixed(2) + '%';
        }
        const notePrecEl = document.getElementById('note-precision');
        if (notePrecEl) {
          notePrecEl.textContent = `${modelName} Model`;
        }

        // Recall
        const recallEl = document.getElementById('perf-recall');
        const recVal = metrics.recall || metrics.recall_score;
        if (recallEl && recVal !== undefined) {
          recallEl.textContent = (recVal * 100).toFixed(2) + '%';
        }
        const noteRecEl = document.getElementById('note-recall');
        if (noteRecEl) {
          noteRecEl.textContent = `${modelName} Model`;
        }

        // F1
        const f1El = document.getElementById('perf-f1');
        const f1Val = metrics.f1 || metrics.f1_score;
        if (f1El && f1Val !== undefined) {
          f1El.textContent = (f1Val * 100).toFixed(2) + '%';
        }
        const noteF1El = document.getElementById('note-f1');
        if (noteF1El) {
          noteF1El.textContent = `${modelName} Model`;
        }

        // AUC-ROC
        const aucEl = document.getElementById('perf-auc');
        const aucVal = metrics.roc_auc || metrics.auc_roc;
        if (aucEl && aucVal !== undefined) {
          aucEl.textContent = (aucVal * 100).toFixed(2) + '%';
        }
        const noteAucEl = document.getElementById('note-auc');
        if (noteAucEl) {
          noteAucEl.textContent = `${modelName} Model`;
        }
      }
    } catch (error) {
      console.error('Error fetching model performance metrics:', error);
    }
  }

  document.addEventListener('DOMContentLoaded', loadPerformanceMetrics);
  // Also load immediately in case DOMContentLoaded has already fired
  if (document.readyState === 'interactive' || document.readyState === 'complete') {
    loadPerformanceMetrics();
  }
})();
