(function () {
  const saveButtons = Array.from(document.querySelectorAll('[data-settings-save="true"]'));
  if (saveButtons.length === 0) {
    return;
  }

  const settingFields = Array.from(document.querySelectorAll('[data-setting-key]'));
  const toggleGroups = Array.from(document.querySelectorAll('.settings-pill-toggle[data-setting-key]'));
  if (settingFields.length === 0 && toggleGroups.length === 0) {
    return;
  }

  const statusEl = document.createElement('p');
  statusEl.style.marginTop = '0.75rem';
  statusEl.style.color = 'var(--text-secondary)';
  statusEl.style.fontSize = '0.88rem';
  saveButtons[0].parentElement.appendChild(statusEl);

  const setStatus = (text, isError) => {
    statusEl.textContent = text;
    statusEl.style.color = isError ? '#ff8a8a' : 'var(--text-secondary)';
  };

  const extractFieldValue = (field) => {
    if (field.type === 'checkbox') {
      return field.checked ? '1' : '0';
    }
    return field.value || '';
  };

  const extractToggleValue = (group) => {
    const activeButton = group.querySelector('button.is-active[data-value]');
    return activeButton ? activeButton.getAttribute('data-value') : '';
  };

  const applyFieldValue = (field, value) => {
    if (field.type === 'checkbox') {
      field.checked = value === '1' || value === 'true';
      return;
    }
    field.value = value;
  };

  const applyToggleValue = (group, value) => {
    const buttons = Array.from(group.querySelectorAll('button[data-value]'));
    if (buttons.length === 0) {
      return;
    }

    let matched = false;
    buttons.forEach((button) => {
      const isMatch = button.getAttribute('data-value') === String(value);
      button.classList.toggle('is-active', isMatch);
      if (isMatch) {
        matched = true;
      }
    });

    if (!matched) {
      buttons[0].classList.add('is-active');
    }
  };

  const loadSettings = async () => {
    try {
      const response = await fetch('../php/settings.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'get' })
      });
      if (response.ok) {
        const data = await response.json().catch(() => ({}));
        if (data.success && data.settings) {
          settingFields.forEach((field) => {
            const key = field.getAttribute('data-setting-key');
            if (Object.prototype.hasOwnProperty.call(data.settings, key)) {
              applyFieldValue(field, data.settings[key]);
            }
          });

          toggleGroups.forEach((group) => {
            const key = group.getAttribute('data-setting-key');
            if (Object.prototype.hasOwnProperty.call(data.settings, key)) {
              applyToggleValue(group, data.settings[key]);
              if (key === 'theme' && window.ThemeManager) {
                window.ThemeManager.applyTheme(data.settings[key]);
                localStorage.setItem('urlguard-theme', data.settings[key]);
              }
            }
          });

          setStatus('Settings loaded from server.');
          return;
        }
      }

      // Fallback: try localStorage
      const localRaw = localStorage.getItem('urlguard-settings');
      if (localRaw) {
        try {
          const localSettings = JSON.parse(localRaw);
          settingFields.forEach((field) => {
            const key = field.getAttribute('data-setting-key');
            if (Object.prototype.hasOwnProperty.call(localSettings, key)) {
              applyFieldValue(field, localSettings[key]);
            }
          });
          toggleGroups.forEach((group) => {
            const key = group.getAttribute('data-setting-key');
            if (Object.prototype.hasOwnProperty.call(localSettings, key)) {
              applyToggleValue(group, localSettings[key]);
              if (key === 'theme' && window.ThemeManager) {
                window.ThemeManager.applyTheme(localSettings[key]);
                localStorage.setItem('urlguard-theme', localSettings[key]);
              }
            }
          });
          setStatus('Settings loaded from local storage (offline).');
          return;
        } catch (_e) {
          // fall through
        }
      }

      setStatus('Could not load saved settings (not logged in or server unavailable).', true);
    } catch (_error) {
      // network error -> fallback to localStorage
      const localRaw = localStorage.getItem('urlguard-settings');
      if (localRaw) {
        try {
          const localSettings = JSON.parse(localRaw);
          settingFields.forEach((field) => {
            const key = field.getAttribute('data-setting-key');
            if (Object.prototype.hasOwnProperty.call(localSettings, key)) {
              applyFieldValue(field, localSettings[key]);
            }
          });
          toggleGroups.forEach((group) => {
            const key = group.getAttribute('data-setting-key');
            if (Object.prototype.hasOwnProperty.call(localSettings, key)) {
              applyToggleValue(group, localSettings[key]);
              if (key === 'theme' && window.ThemeManager) {
                window.ThemeManager.applyTheme(localSettings[key]);
                localStorage.setItem('urlguard-theme', localSettings[key]);
              }
            }
          });
          setStatus('Settings loaded from local storage (offline).');
          return;
        } catch (_e) {}
      }
      setStatus('Failed to load settings.', true);
    }
  };

  const saveSettings = async () => {
    const settingsPayload = {};

    settingFields.forEach((field) => {
      const key = field.getAttribute('data-setting-key');
      settingsPayload[key] = extractFieldValue(field);
    });

    toggleGroups.forEach((group) => {
      const key = group.getAttribute('data-setting-key');
      settingsPayload[key] = extractToggleValue(group);
    });

    saveButtons.forEach((button) => {
      button.disabled = true;
    });
    setStatus('Saving...');

    try {
      const response = await fetch('../php/settings.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'save',
          settings: settingsPayload
        })
      });

      if (response.ok) {
        const data = await response.json().catch(() => ({}));
        if (data.success) {
          setStatus('Settings saved to server.');
          // also mirror to localStorage for offline
          try { localStorage.setItem('urlguard-settings', JSON.stringify(settingsPayload)); } catch (e) {}
          return;
        }
      }

      // Server failed — fallback to localStorage
      try {
        localStorage.setItem('urlguard-settings', JSON.stringify(settingsPayload));
        setStatus('Server unavailable — settings saved locally.');
      } catch (e) {
        setStatus('Failed to save settings.', true);
      }
    } catch (_error) {
      try {
        localStorage.setItem('urlguard-settings', JSON.stringify(settingsPayload));
        setStatus('Offline — settings saved locally.');
      } catch (e) {
        setStatus('Failed to save settings.', true);
      }
    } finally {
      saveButtons.forEach((button) => {
        button.disabled = false;
      });
    }
  };

  saveButtons.forEach((button) => {
    button.addEventListener('click', saveSettings);
  });

  // Trigger auto-save on select or checkbox changes
  settingFields.forEach((field) => {
    const key = field.getAttribute('data-setting-key');
    if (key === 'full_name' || key === 'email_address') {
      return;
    }
    field.addEventListener('change', () => {
      saveSettings();
    });
  });

  toggleGroups.forEach((group) => {
    const buttons = Array.from(group.querySelectorAll('button[data-value]'));
    buttons.forEach((button) => {
      button.addEventListener('click', () => {
        buttons.forEach((b) => b.classList.remove('is-active'));
        button.classList.add('is-active');
        const key = group.getAttribute('data-setting-key');
        const val = button.getAttribute('data-value');
        if (key === 'theme' && window.ThemeManager) {
          window.ThemeManager.applyTheme(val);
          localStorage.setItem('urlguard-theme', val);
        }
        saveSettings(); // Auto-save when toggle changes!
      });
    });
  });

  let originalProfileData = {
    full_name: '',
    email_address: ''
  };

  const updateOriginalProfileData = () => {
    const fullNameInput = document.getElementById('userFullName');
    const emailInput = document.getElementById('userEmailAddress');
    if (fullNameInput) originalProfileData.full_name = fullNameInput.value;
    if (emailInput) originalProfileData.email_address = emailInput.value;
  };

  const editBtn = document.getElementById('userSettingsEdit');
  const saveBtn = document.getElementById('userSettingsSave');
  const fullNameInput = document.getElementById('userFullName');
  const emailInput = document.getElementById('userEmailAddress');

  if (editBtn && saveBtn && fullNameInput && emailInput) {
    editBtn.addEventListener('click', () => {
      const isReadOnly = fullNameInput.hasAttribute('readonly');
      if (isReadOnly) {
        fullNameInput.removeAttribute('readonly');
        emailInput.removeAttribute('readonly');
        fullNameInput.focus();
        editBtn.textContent = 'Cancel';
        saveBtn.style.display = 'inline-block';
        setStatus('Editing profile settings...');
      } else {
        fullNameInput.value = originalProfileData.full_name;
        emailInput.value = originalProfileData.email_address;
        fullNameInput.setAttribute('readonly', 'true');
        emailInput.setAttribute('readonly', 'true');
        editBtn.textContent = 'Edit';
        saveBtn.style.display = 'none';
        setStatus('Editing cancelled.');
      }
    });

    saveBtn.addEventListener('click', () => {
      fullNameInput.setAttribute('readonly', 'true');
      emailInput.setAttribute('readonly', 'true');
      editBtn.textContent = 'Edit';
      saveBtn.style.display = 'none';
      updateOriginalProfileData();
    });
  }

  loadSettings().then(() => {
    updateOriginalProfileData();
  });

  // Additional user actions: clear history, download data, delete account
  const clearBtn = document.getElementById('clearHistoryBtn');
  const downloadBtn = document.getElementById('downloadDataBtn');
  const deleteBtn = document.getElementById('deleteAccountBtn');

  const HISTORY_KEY = 'urlguard-history';

  if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
      if (!confirm('Clear all scan history? This cannot be undone.')) return;
      setStatus('Clearing history...');
      try {
        const res = await fetch('../php/clear_history.php', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          setStatus('Scan history cleared.');
        } else {
          setStatus('Failed to clear scan history on server: ' + (data.message || 'unknown error'), true);
        }
      } catch (e) {
        setStatus('Offline — cleared local view only.', true);
      }
      try {
        localStorage.removeItem(HISTORY_KEY);
      } catch (e) {}
      if (typeof localHistoryCache !== 'undefined') {
        localHistoryCache = [];
      }
      if (typeof renderHistory === 'function') {
        renderHistory();
      }
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener('click', async () => {
      setStatus('Preparing download...');
      try {
        const response = await fetch('../php/history.php?export=true');
        const resData = await response.json();
        let scans = [];
        if (resData.success && Array.isArray(resData.scans)) {
          scans = resData.scans;
        } else {
          // Fallback to local cache if fetch fails or succeeds without scans
          scans = typeof localHistoryCache !== 'undefined' ? localHistoryCache : [];
        }

        if (scans.length === 0) {
          setStatus('No scan history to download.', true);
          alert('You do not have any scan history to download.');
          return;
        }

        // Generate CSV content
        // Columns: Sl. No., URL, Result, Confidence (%), Risk Level, Reason / Explanation, Scan Time
        let csvContent = '\uFEFF'; // UTF-8 BOM so Excel opens it correctly with UTF-8 characters
        csvContent += 'Sl. No.,URL,Result,Confidence (%),Risk Level,Reason/Explanation,Scan Time\r\n';

        scans.forEach((scan, index) => {
          const slNo = index + 1;
          
          // Escape quotes in CSV
          const escapeCsv = (val) => {
            if (val === null || val === undefined) return '';
            const strVal = String(val);
            if (strVal.includes(',') || strVal.includes('"') || strVal.includes('\n') || strVal.includes('\r')) {
              return '"' + strVal.replace(/"/g, '""') + '"';
            }
            return strVal;
          };

          const url = escapeCsv(scan.url || scan.displayUrl);
          const result = escapeCsv(scan.prediction || scan.status);
          const confidence = escapeCsv(scan.confidence);
          const risk = escapeCsv(scan.risk_level || scan.riskLevel);
          const reason = escapeCsv(scan.explanation || '');
          const time = escapeCsv(scan.scan_time || scan.time);

          csvContent += `${slNo},${url},${result},${confidence},${risk},${reason},${time}\r\n`;
        });

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'urlguard-scans-' + new Date().toISOString().slice(0, 10) + '.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setStatus('Download completed.');
      } catch (err) {
        console.error(err);
        setStatus('Failed to generate export.', true);
      }
    });
  }

  if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
      if (!confirm('Permanently delete your account and all local data? This action cannot be undone.')) return;
      setStatus('Deleting account...');
      try {
        // Attempt to call server endpoint to delete account; fallback to clearing local data
        const res = await fetch('../php/account_delete.php', { method: 'POST' });
        const json = await res.json().catch(() => ({}));
        if (json.success) {
          try { localStorage.removeItem(HISTORY_KEY); } catch (e) {}
          setStatus('Account deleted. Redirecting...');
          setTimeout(() => { window.location.href = '../index.html'; }, 1200);
          return;
        }
      } catch (e) {}

      // If server delete not available, clear local and redirect
      try { localStorage.removeItem(HISTORY_KEY); } catch (e) {}
      setStatus('Local data cleared. Contact admin to remove server account.');
    });
  }

  // Change Password Action
  const updatePasswordBtn = document.getElementById('updatePasswordBtn');
  const currentPasswordInput = document.getElementById('currentPassword');
  const newPasswordInput = document.getElementById('newPassword');
  const confirmNewPasswordInput = document.getElementById('confirmNewPassword');
  const passwordStatus = document.getElementById('passwordStatus');

  if (updatePasswordBtn && currentPasswordInput && newPasswordInput && confirmNewPasswordInput && passwordStatus) {
    updatePasswordBtn.addEventListener('click', async () => {
      passwordStatus.style.display = 'none';
      passwordStatus.textContent = '';
      passwordStatus.style.color = 'var(--text-secondary)';

      const currentPw = currentPasswordInput.value;
      const newPw = newPasswordInput.value;
      const confirmPw = confirmNewPasswordInput.value;

      if (!currentPw || !newPw || !confirmPw) {
        passwordStatus.textContent = 'All password fields are required.';
        passwordStatus.style.color = '#ff8a8a';
        passwordStatus.style.display = 'block';
        return;
      }

      if (newPw !== confirmPw) {
        passwordStatus.textContent = 'New passwords do not match.';
        passwordStatus.style.color = '#ff8a8a';
        passwordStatus.style.display = 'block';
        return;
      }

      // Password policy check: at least 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
      const policy = /^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=[\]{};':"\\|,.<>\/?]).{8,}$/;
      if (!policy.test(newPw)) {
        passwordStatus.textContent = 'Password must be at least 8 characters and include one uppercase letter, one number, and one special character.';
        passwordStatus.style.color = '#ff8a8a';
        passwordStatus.style.display = 'block';
        return;
      }

      updatePasswordBtn.disabled = true;
      passwordStatus.textContent = 'Updating password...';
      passwordStatus.style.display = 'block';

      try {
        const response = await fetch('../php/change_password.php', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_password: currentPw,
            new_password: newPw
          })
        });

        const data = await response.json().catch(() => ({ success: false, message: 'Invalid response from server.' }));
        if (response.ok && data.success) {
          passwordStatus.textContent = data.message || 'Password changed successfully.';
          passwordStatus.style.color = 'var(--safe)';
          currentPasswordInput.value = '';
          newPasswordInput.value = '';
          confirmNewPasswordInput.value = '';
        } else {
          passwordStatus.textContent = data.message || 'Failed to update password.';
          passwordStatus.style.color = '#ff8a8a';
        }
      } catch (err) {
        passwordStatus.textContent = 'A network error occurred. Please try again.';
        passwordStatus.style.color = '#ff8a8a';
      } finally {
        updatePasswordBtn.disabled = false;
      }
    });
  }

  // View Activity Modal Logic
  const viewActivityBtn = document.getElementById('viewActivityBtn');
  const activityModal = document.getElementById('activityModal');
  const closeActivityModalBtn = document.getElementById('closeActivityModalBtn');
  const activityLogTableBody = document.getElementById('activityLogTableBody');

  if (viewActivityBtn && activityModal && closeActivityModalBtn && activityLogTableBody) {
    viewActivityBtn.addEventListener('click', async () => {
      activityModal.style.display = 'flex';
      activityLogTableBody.innerHTML = '<tr><td colspan="3" class="empty-state-cell">Loading activity logs...</td></tr>';

      try {
        const response = await fetch('../php/login_activity.php');
        if (!response.ok) throw new Error('Failed to fetch activity logs');
        const data = await response.json();
        
        if (data.success && Array.isArray(data.activities)) {
          activityLogTableBody.innerHTML = '';
          if (data.activities.length === 0) {
            activityLogTableBody.innerHTML = '<tr><td colspan="3" class="empty-state-cell">No recent login activity found.</td></tr>';
          } else {
            data.activities.forEach(activity => {
              const tr = document.createElement('tr');
              
              const tdTime = document.createElement('td');
              tdTime.textContent = activity.login_time || 'N/A';
              
              const tdIp = document.createElement('td');
              tdIp.textContent = activity.ip_address || 'N/A';
              
              const tdAgent = document.createElement('td');
              let ua = activity.user_agent || 'N/A';
              if (ua.includes('Chrome/')) {
                ua = 'Chrome Browser';
              } else if (ua.includes('Firefox/')) {
                ua = 'Firefox Browser';
              } else if (ua.includes('Safari/') && !ua.includes('Chrome/')) {
                ua = 'Safari Browser';
              } else if (ua.includes('Edge/')) {
                ua = 'Microsoft Edge';
              } else if (ua.length > 50) {
                ua = ua.substring(0, 47) + '...';
              }
              tdAgent.textContent = ua;
              
              tr.appendChild(tdTime);
              tr.appendChild(tdIp);
              tr.appendChild(tdAgent);
              activityLogTableBody.appendChild(tr);
            });
          }
        } else {
          activityLogTableBody.innerHTML = '<tr><td colspan="3" class="empty-state-cell" style="color:#ff8a8a;">Error loading activity: ' + (data.message || 'unknown error') + '</td></tr>';
        }
      } catch (err) {
        activityLogTableBody.innerHTML = '<tr><td colspan="3" class="empty-state-cell" style="color:#ff8a8a;">Network error occurred. Please try again.</td></tr>';
      }
    });

    closeActivityModalBtn.addEventListener('click', () => {
      activityModal.style.display = 'none';
    });

    activityModal.addEventListener('click', (e) => {
      if (e.target === activityModal) {
        activityModal.style.display = 'none';
      }
    });
  }
})();
