/* ============================================================
   HOSTX VIP — MAIN JAVASCRIPT
   ============================================================ */

// ============================================================
// 1. LOADER
// ============================================================
(function() {
  function hideLoader() {
    const el = document.getElementById('loader');
    if (el) el.classList.add('hidden');
  }
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(hideLoader, 200);
  } else {
    document.addEventListener('DOMContentLoaded', () => setTimeout(hideLoader, 200));
  }
  window.addEventListener('load', () => setTimeout(hideLoader, 100));
})();

// ============================================================
// 2. TOASTS
// ============================================================
function showToast(msg, type = 'info') {
  const container = document.getElementById('toasts');
  if (!container) return;
  const t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transform = 'translateX(20px)';
    t.style.transition = 'all 0.3s ease';
    setTimeout(() => t.remove(), 300);
  }, 3500);
}

// ============================================================
// 3. DROPDOWNS
// ============================================================
function toggleDropdown(event, btn) {
  if (event) event.stopPropagation();
  const wrap = btn.closest('.dd-wrap');
  if (!wrap) return;
  const isOpen = wrap.classList.contains('open');
  document.querySelectorAll('.dd-wrap.open').forEach(w => {
    if (w !== wrap) w.classList.remove('open');
  });
  wrap.classList.toggle('open', !isOpen);
}
document.addEventListener('click', (e) => {
  if (!e.target.closest('.dd-wrap')) {
    document.querySelectorAll('.dd-wrap.open').forEach(w => w.classList.remove('open'));
  }
});

// ============================================================
// 4. PASSWORD TOGGLE
// ============================================================
function togglePass(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
  } else {
    input.type = 'password';
    btn.textContent = '👁️';
  }
}

// ============================================================
// 5. NOTIFICATIONS
// ============================================================
function loadNotifications() {
  const list = document.getElementById('notif-list');
  const badge = document.getElementById('notif-badge');
  if (!list) return;
  fetch('/api/notifications')
    .then(r => r.json())
    .then(data => {
      if (!data.success) return;
      if (badge) {
        if (data.unread_count > 0) {
          badge.style.display = 'flex';
          badge.textContent = data.unread_count > 9 ? '9+' : data.unread_count;
        } else {
          badge.style.display = 'none';
        }
      }
      if (!data.notifications || data.notifications.length === 0) {
        list.innerHTML = '<div class="empty-mini">No notifications yet.</div>';
        return;
      }
      let html = '';
      data.notifications.forEach(n => {
        html += `<div class="notif-item ${n.is_read ? '' : 'unread'}" onclick="deleteNotif(${n.id}, event)">
          <div class="notif-item-title"><b>${escapeHtml(n.title)}</b><span>${n.created_at.split('.')[0]}</span></div>
          <div class="notif-item-msg">${escapeHtml(n.message)}</div>
        </div>`;
      });
      list.innerHTML = html;
    })
    .catch(() => {
      if (list) list.innerHTML = '<div class="empty-mini">Failed to load.</div>';
    });
}

function deleteNotif(id, event) {
  if (event) event.stopPropagation();
  fetch(`/api/notifications/${id}/delete`, { method: 'POST' })
    .then(r => r.json())
    .then(() => loadNotifications());
}

function clearAllNotifs(event) {
  if (event) event.stopPropagation();
  fetch('/api/notifications/clear-all', { method: 'POST' })
    .then(r => r.json())
    .then(() => {
      showToast('All notifications cleared.', 'success');
      loadNotifications();
    });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

if (document.getElementById('notif-list')) {
  loadNotifications();
  setInterval(loadNotifications, 30000);
}

// ============================================================
// 6. FORGOT PASSWORD MODAL
// ============================================================
function openForgotModal() {
  const m = document.getElementById('forgot-modal');
  if (m) {
    m.style.display = 'flex';
    showFpStep(1);
    loadCaptcha();
  }
}
function closeForgotModal() {
  const m = document.getElementById('forgot-modal');
  if (m) m.style.display = 'none';
}
function showFpStep(step) {
  ['fp-step1', 'fp-step2', 'fp-step3'].forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) el.style.display = (i + 1 === step) ? 'block' : 'none';
  });
  ['sb1', 'sb2', 'sb3'].forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) {
      el.className = 'stepb' + (i + 1 <= step ? ' active' : '') + (i + 1 < step ? ' done' : '');
    }
  });
}
function loadCaptcha() {
  const box = document.getElementById('fp-captcha');
  if (!box) return;
  box.textContent = 'Loading...';
  fetch('/api/forgot-password/captcha')
    .then(r => r.json())
    .then(data => {
      box.textContent = data.question || 'Error';
      const ans = document.getElementById('fp-captcha-answer');
      if (ans) ans.value = '';
    })
    .catch(() => { box.textContent = 'Error loading'; });
}
function fpSubmitCaptcha() {
  const ans = (document.getElementById('fp-captcha-answer') || {}).value || '';
  const err = document.getElementById('fp-cap-err');
  if (err) err.style.display = 'none';
  if (!ans) {
    if (err) { err.textContent = 'Enter answer.'; err.style.display = 'block'; }
    return;
  }
  fetch('/api/forgot-password/verify-captcha', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer: ans })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) showFpStep(2);
      else {
        if (err) { err.textContent = data.message || 'Incorrect.'; err.style.display = 'block'; }
        loadCaptcha();
      }
    })
    .catch(() => {
      if (err) { err.textContent = 'Connection error.'; err.style.display = 'block'; }
    });
}
function fpSubmitEmail() {
  const email = (document.getElementById('fp-email') || {}).value || '';
  const err = document.getElementById('fp-email-err');
  if (err) err.style.display = 'none';
  if (!email) {
    if (err) { err.textContent = 'Enter email.'; err.style.display = 'block'; }
    return;
  }
  fetch('/api/forgot-password/verify-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim().toLowerCase() })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) showFpStep(3);
      else {
        if (err) { err.textContent = data.message || 'Not registered.'; err.style.display = 'block'; }
      }
    })
    .catch(() => {
      if (err) { err.textContent = 'Connection error.'; err.style.display = 'block'; }
    });
}
function fpSubmitReset() {
  const pw = (document.getElementById('fp-new-pass') || {}).value || '';
  const cp = (document.getElementById('fp-conf-pass') || {}).value || '';
  const err = document.getElementById('fp-pw-err');
  if (err) err.style.display = 'none';
  if (!pw || !cp) {
    if (err) { err.textContent = 'All fields required.'; err.style.display = 'block'; }
    return;
  }
  if (pw !== cp) {
    if (err) { err.textContent = 'Passwords do not match.'; err.style.display = 'block'; }
    return;
  }
  if (pw.length < 6) {
    if (err) { err.textContent = 'Min 6 characters.'; err.style.display = 'block'; }
    return;
  }
  fetch('/api/forgot-password/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pw, confirm_password: cp })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('Password updated! Please sign in.', 'success');
        closeForgotModal();
      } else {
        if (err) { err.textContent = data.message || 'Error.'; err.style.display = 'block'; }
      }
    })
    .catch(() => {
      if (err) { err.textContent = 'Connection error.'; err.style.display = 'block'; }
    });
}

// ============================================================
// 7. SERVER ACTIONS (Start/Stop/Restart)
// ============================================================
function serverAction(serverId, action) {
  const btn = document.getElementById('btn-' + action);
  const originalText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Please wait...';
  }

  fetch(`/api/servers/${serverId}/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: action })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || 'Success!', 'success');
        updateStatusBadge(data.status, data.pid);
        updatePidBadge(data.pid);
        setTimeout(() => window.location.reload(), 900);
      } else {
        // Special errors
        if (data.plan_required || data.redirect_url === '/packages') {
          showToast(data.message || 'Purchase a plan first.', 'warning');
          setTimeout(() => window.location.href = '/packages', 1200);
          return;
        }
        if (data.no_entry_file || data.redirect_url) {
          const modal = document.getElementById('no-entry-modal');
          if (modal) modal.style.display = 'flex';
          else if (data.redirect_url) window.location.href = data.redirect_url;
        } else if (data.package_required && data.missing_packages) {
          const names = data.missing_packages.map(p => p.name).join(', ');
          showToast('Missing packages: ' + names, 'warning');
        } else {
          showToast(data.message || 'Action failed.', 'danger');
        }
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      }
    })
    .catch(err => {
      showToast('Network error: ' + err.message, 'danger');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });
}

function updateStatusBadge(status, pid) {
  const badge = document.getElementById('status-badge');
  if (!badge) return;
  if (status === 'running') {
    badge.className = 'status status-running';
    badge.innerHTML = '🟢 RUNNING';
  } else if (status === 'package_required') {
    badge.className = 'status status-warn';
    badge.innerHTML = '🟡 SETUP';
  } else if (status === 'expired') {
    badge.className = 'status status-expired';
    badge.innerHTML = '🔴 EXPIRED';
  } else {
    badge.className = 'status status-stopped';
    badge.innerHTML = '🔴 STOPPED';
  }
}
function updatePidBadge(pid) {
  const badge = document.getElementById('pid-badge');
  if (!badge) return;
  if (pid && pid > 0) {
    badge.textContent = 'PID: ' + pid;
    badge.className = 'pid-badge pid-on';
  } else {
    badge.textContent = 'PID: Offline';
    badge.className = 'pid-badge';
  }
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-text');
  if (pid && pid > 0) {
    if (dot) dot.classList.add('on');
    if (txt) { txt.classList.add('on'); txt.textContent = 'Running'; }
  } else {
    if (dot) dot.classList.remove('on');
    if (txt) { txt.classList.remove('on'); txt.textContent = 'Offline'; }
  }
}

// ============================================================
// 8. LIVE LOGS
// ============================================================
let logStreamInterval = null;
function startLogStream(serverId, startTime) {
  const term = document.getElementById('terminal');
  if (!term) return;
  const tick = document.getElementById('uptime-tick');

  function fetchLogs() {
    fetch(`/api/servers/${serverId}/logs`)
      .then(r => r.json())
      .then(data => {
        if (data.raw_logs) {
          const lines = data.raw_logs.split('\n');
          let html = '';
          lines.slice(-200).forEach(line => {
            if (!line.trim()) return;
            let cls = 'log-info';
            const lower = line.toLowerCase();
            if (lower.includes('error') || lower.includes('traceback') || lower.includes('exception')) cls = 'log-error';
            else if (lower.includes('warning') || lower.includes('warn')) cls = 'log-warning';
            else if (lower.includes('success') || lower.includes('started') || lower.includes('running')) cls = 'log-success';
            else if (lower.includes('stopping') || lower.includes('stopped')) cls = 'log-running';
            html += `<div class="log-line ${cls}">${escapeHtml(line)}</div>`;
          });
          term.innerHTML = html || '<div class="log-line log-info">[INFO] No logs yet. Start the server to see output.</div>';
          term.scrollTop = term.scrollHeight;
        }
        updatePidBadge(data.pid);
        updateStatusBadge(data.status, data.pid);

        if (data.status === 'running' && data.start_time > 0) {
          const secs = Math.floor(Date.now() / 1000 - data.start_time);
          const h = Math.floor(secs / 3600);
          const m = Math.floor((secs % 3600) / 60);
          const s = secs % 60;
          if (tick) {
            tick.textContent = String(h).padStart(2, '0') + ':' +
              String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
          }
        } else {
          if (tick) tick.textContent = '00:00:00';
        }
      })
      .catch(() => {});
  }
  fetchLogs();
  if (logStreamInterval) clearInterval(logStreamInterval);
  logStreamInterval = setInterval(fetchLogs, 3000);
}

function clearLogs(serverId) {
  if (!confirm('Clear all logs for this server?')) return;
  fetch(`/api/servers/${serverId}/logs/clear`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('Logs cleared.', 'success');
        const term = document.getElementById('terminal');
        if (term) term.innerHTML = '<div class="log-line log-info">[INFO] Logs cleared.</div>';
      } else {
        showToast(data.message || 'Failed.', 'danger');
      }
    });
}

// ============================================================
// 9. INTERACTIVE TERMINAL
// ============================================================
function quickCommand(cmd) {
  const inp = document.getElementById('terminal-input');
  if (inp) { inp.value = cmd; inp.focus(); }
}

function sendTerminalCommand() {
  const input = document.getElementById('terminal-input');
  if (!input || !input.value.trim()) return;
  const cmd = input.value.trim();
  input.value = '';

  const term = document.getElementById('interactive-terminal');
  if (!term) return;
  term.innerHTML += `<div class="log-line log-info">$ ${escapeHtml(cmd)}</div>`;
  term.scrollTop = term.scrollHeight;

  const sid = term.dataset.serverId;
  fetch(`/api/servers/${sid}/terminal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command: cmd })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        const lines = (data.output || '').split('\n');
        lines.forEach(line => {
          if (line.trim()) {
            const cls = line.toLowerCase().includes('error') ? 'log-error' : 'log-success';
            term.innerHTML += `<div class="log-line ${cls}">${escapeHtml(line)}</div>`;
          }
        });
      } else {
        term.innerHTML += `<div class="log-line log-error">Error: ${escapeHtml(data.message)}</div>`;
      }
      term.scrollTop = term.scrollHeight;
    })
    .catch(() => {
      term.innerHTML += '<div class="log-line log-error">Network error</div>';
    });
}

function clearTerminal() {
  const term = document.getElementById('interactive-terminal');
  if (term) term.innerHTML = '<div class="log-line log-info">[INFO] Terminal cleared.</div>';
}

// ============================================================
// 10. RENEW / EXTEND SERVER
// ============================================================
function submitRenew(serverId, isExpired) {
  const selector = isExpired ? 'input[name="renew_pkg_exp"]:checked' : 'input[name="renew_pkg"]:checked';
  const selected = document.querySelector(selector);
  if (!selected) {
    showToast('Please select a package.', 'warning');
    return;
  }
  const btn = document.querySelector('#renew-modal .btn-primary, .modal-card .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = 'Processing...'; }

  fetch(`/api/servers/${serverId}/renew`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ package_id: selected.value })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || 'Renewed!', 'success');
        setTimeout(() => window.location.reload(), 900);
      } else {
        showToast(data.message || 'Renewal failed.', 'danger');
        if (btn) { btn.disabled = false; btn.textContent = 'Confirm Extension'; }
      }
    })
    .catch(() => {
      showToast('Network error.', 'danger');
      if (btn) { btn.disabled = false; btn.textContent = 'Confirm Extension'; }
    });
}

// ============================================================
// 11. FILE MANAGER
// ============================================================
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function uploadFile(serverId, input, isZip) {
  if (!input.files || input.files.length === 0) return;

  const files = input.files;
  const fd = new FormData();
  const urlParams = new URLSearchParams(window.location.search);
  fd.append('path', urlParams.get('path') || '');
  for (let i = 0; i < files.length; i++) {
    fd.append('files', files[i]);
  }

  const modal = document.getElementById('up-modal');
  const title = document.getElementById('up-title');
  const icon = document.getElementById('up-icon');
  const sub = document.getElementById('up-sub');
  const bar = document.getElementById('up-bar');
  const pct = document.getElementById('up-pct');
  const size = document.getElementById('up-size');

  if (modal) modal.style.display = 'flex';
  if (title) title.textContent = isZip ? 'Uploading & Extracting ZIP...' : 'Uploading Files...';
  if (icon) icon.textContent = isZip ? '📦' : '📤';
  if (sub) sub.textContent = 'Please wait.';
  if (bar) bar.style.width = '0%';

  const xhr = new XMLHttpRequest();
  xhr.open('POST', `/api/servers/${serverId}/files/upload`, true);

  xhr.upload.onprogress = function(e) {
    if (e.lengthComputable) {
      const percent = Math.round((e.loaded / e.total) * 100);
      if (bar) bar.style.width = percent + '%';
      if (pct) pct.textContent = percent + '%';
      if (size) size.textContent = formatBytes(e.loaded) + ' / ' + formatBytes(e.total);
      if (sub && percent >= 100) sub.textContent = 'Processing on server...';
    }
  };

  xhr.onload = function() {
    if (modal) modal.style.display = 'none';
    try {
      const data = JSON.parse(xhr.responseText);
      if (data.success) {
        showToast(data.message || 'Uploaded!', 'success');
        setTimeout(() => window.location.reload(), 700);
      } else {
        showToast(data.message || 'Upload failed.', 'danger');
      }
    } catch {
      showToast('Invalid server response.', 'danger');
    }
    input.value = '';
  };

  xhr.onerror = function() {
    if (modal) modal.style.display = 'none';
    showToast('Network error during upload.', 'danger');
    input.value = '';
  };

  xhr.send(fd);
}

function promptFolder(serverId) {
  const name = prompt('New folder name:');
  if (!name) return;
  const fd = new FormData();
  const urlParams = new URLSearchParams(window.location.search);
  fd.append('path', urlParams.get('path') || '');
  fd.append('folder_name', name);
  fetch(`/api/servers/${serverId}/files/create-folder`, { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message, 'success');
        setTimeout(() => window.location.reload(), 600);
      } else showToast(data.message, 'danger');
    });
}

function promptFile(serverId) {
  const name = prompt('New file name (e.g. config.py):');
  if (!name) return;
  const fd = new FormData();
  const urlParams = new URLSearchParams(window.location.search);
  fd.append('path', urlParams.get('path') || '');
  fd.append('file_name', name);
  fetch(`/api/servers/${serverId}/files/create-file`, { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message, 'success');
        setTimeout(() => window.location.reload(), 600);
      } else showToast(data.message, 'danger');
    });
}

function openEditor(serverId, path) {
  const modal = document.getElementById('editor-modal');
  const nameEl = document.getElementById('ed-file');
  const pathEl = document.getElementById('ed-path');
  const contentEl = document.getElementById('ed-content');
  if (!modal) return;

  if (nameEl) nameEl.textContent = path.split('/').pop();
  if (pathEl) pathEl.value = path;
  if (contentEl) contentEl.value = 'Loading...';
  modal.style.display = 'flex';

  fetch(`/api/servers/${serverId}/files/read?path=${encodeURIComponent(path)}`)
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        if (contentEl) contentEl.value = data.content || '';
      } else {
        if (contentEl) contentEl.value = '// Error: ' + (data.message || 'Could not load.');
      }
    })
    .catch(() => {
      if (contentEl) contentEl.value = '// Failed to load file.';
    });
}

function saveEditor(serverId) {
  const pathEl = document.getElementById('ed-path');
  const contentEl = document.getElementById('ed-content');
  const btn = document.getElementById('ed-save');
  if (!pathEl || !contentEl) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }

  fetch(`/api/servers/${serverId}/files/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: pathEl.value, content: contentEl.value })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('File saved!', 'success');
        const m = document.getElementById('editor-modal');
        if (m) m.style.display = 'none';
      } else {
        showToast(data.message || 'Save failed.', 'danger');
      }
      if (btn) { btn.disabled = false; btn.textContent = '💾 Save'; }
    })
    .catch(() => {
      showToast('Network error.', 'danger');
      if (btn) { btn.disabled = false; btn.textContent = '💾 Save'; }
    });
}

function deleteItem(serverId, path) {
  if (!confirm(`Delete "${path}"? This cannot be undone.`)) return;
  fetch(`/api/servers/${serverId}/files/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('Deleted.', 'success');
        setTimeout(() => window.location.reload(), 600);
      } else showToast(data.message, 'danger');
    });
}

function renameItem(serverId, path) {
  const oldName = path.split('/').pop();
  const newName = prompt(`Rename "${oldName}" to:`, oldName);
  if (!newName || newName === oldName) return;
  fetch(`/api/servers/${serverId}/files/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_path: path, new_name: newName })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message, 'success');
        setTimeout(() => window.location.reload(), 600);
      } else showToast(data.message, 'danger');
    });
}

function unzipItem(serverId, path) {
  if (!confirm(`Extract "${path}"?`)) return;
  fetch(`/api/servers/${serverId}/files/unzip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(data.message || 'Extracted!', 'success');
        setTimeout(() => window.location.reload(), 900);
      } else showToast(data.message, 'danger');
    });
}

// ============================================================
// 12. PAYMENT / CHECKOUT
// ============================================================
function copyUpiId() {
  const el = document.getElementById('upi-id-display');
  if (!el) return;
  const text = el.dataset.upi || el.textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast('UPI ID copied!', 'success');
  }).catch(() => {
    // Fallback
    const range = document.createRange();
    range.selectNode(el);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand('copy');
    showToast('UPI ID copied!', 'success');
  });
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied!', 'success');
  });
}

function selectPayMethod(el) {
  document.querySelectorAll('.pay-method-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
}

function selectManualMethod(upiId, appName) {
  const inp = document.getElementById('manual-upi-id');
  if (inp) inp.value = upiId;
  document.querySelectorAll('.pay-method-card').forEach(c => c.classList.remove('selected'));
  const card = document.querySelector(`.pay-method-card[data-upi="${upiId}"]`);
  if (card) card.classList.add('selected');
}

// Auto-poll payment status (FamPay auto)
let paymentPollInterval = null;
function startPaymentPoll(orderId) {
  if (!orderId) return;
  const statusEl = document.getElementById('payment-status-text');
  const statusSub = document.getElementById('payment-status-sub');
  let attempts = 0;
  const maxAttempts = 200; // 200 * 3 sec = 10 min

  paymentPollInterval = setInterval(() => {
    attempts++;
    if (attempts > maxAttempts) {
      clearInterval(paymentPollInterval);
      if (statusEl) statusEl.textContent = '⏰ Payment timeout';
      if (statusSub) statusSub.textContent = 'Please contact support if amount was deducted.';
      return;
    }

    fetch(`/api/payment/check/${orderId}`)
      .then(r => r.json())
      .then(data => {
        if (data.success && data.status === 'paid') {
          clearInterval(paymentPollInterval);
          if (statusEl) statusEl.textContent = '✅ Payment Successful!';
          if (statusSub) statusSub.textContent = 'Balance added. Redirecting...';
          showToast('Payment successful!', 'success');
          setTimeout(() => window.location.href = data.redirect || '/dashboard', 1500);
        }
      })
      .catch(() => {});
  }, 3000);
}

// Manual payment — transaction ID submit
function submitTransactionId(orderId) {
  const inp = document.getElementById('txn-id-input');
  if (!inp || !inp.value.trim()) {
    showToast('Please enter transaction ID.', 'warning');
    return;
  }
  const btn = document.getElementById('txn-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Submitting...'; }

  fetch(`/api/payment/manual/${orderId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transaction_id: inp.value.trim() })
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('Thank you! Payment is being processed.', 'success');
        const form = document.getElementById('txn-form');
        const done = document.getElementById('txn-done');
        if (form) form.style.display = 'none';
        if (done) done.style.display = 'block';
        setTimeout(() => window.location.href = '/dashboard', 3000);
      } else {
        showToast(data.message || 'Submit failed.', 'danger');
        if (btn) { btn.disabled = false; btn.textContent = 'Submit Transaction ID'; }
      }
    })
    .catch(() => {
      showToast('Network error.', 'danger');
      if (btn) { btn.disabled = false; btn.textContent = 'Submit Transaction ID'; }
    });
}

// ============================================================
// 13. ADMIN — USER EDIT
// ============================================================
function openEditUser(id, name, username, email, bio, coins, role, status, perms, isSuper) {
  const modal = document.getElementById('edit-user-modal');
  if (!modal) return;
  const form = document.getElementById('edit-user-form');
  if (form) form.action = `/admin/users/${id}/update`;

  const nameEl = document.getElementById('eu_name'); if (nameEl) nameEl.value = name;
  const userEl = document.getElementById('eu_user'); if (userEl) userEl.value = username;
  const emailEl = document.getElementById('eu_email'); if (emailEl) emailEl.value = email;
  const bioEl = document.getElementById('eu_bio'); if (bioEl) bioEl.value = bio || '';
  const coinsEl = document.getElementById('eu_coins'); if (coinsEl) coinsEl.value = coins;
  const passEl = document.getElementById('eu_pass'); if (passEl) passEl.value = '';

  const roleEl = document.getElementById('eu_role');
  if (roleEl) {
    roleEl.value = isSuper ? 'super_admin' : role;
    togglePermBlock(roleEl.value);
  }
  const statusEl = document.getElementById('eu_status'); if (statusEl) statusEl.value = status;

  // Permissions
  if (perms) {
    const list = perms === 'all' ? ['manage_users','manage_coins','manage_files','manage_settings','manage_announcements','manage_broadcasts','view_logs'] : perms.split(',');
    ['manage_users','manage_coins','manage_files','manage_settings','manage_announcements','manage_broadcasts','view_logs'].forEach(p => {
      const el = document.getElementById('p_' + p.replace('manage_', '').replace('view_', ''));
      if (el) el.checked = list.indexOf(p) !== -1;
    });
  }
  modal.style.display = 'flex';
}

function togglePermBlock(roleVal) {
  const block = document.getElementById('perm-block');
  if (block) block.style.display = (roleVal === 'admin') ? 'block' : 'none';
}

function closeEditUser() {
  const m = document.getElementById('edit-user-modal');
  if (m) m.style.display = 'none';
}

// ============================================================
// 14. ADMIN — LOGO PREVIEW
// ============================================================
function previewLogo(input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const img = document.getElementById('logo-preview');
    if (img) { img.src = e.target.result; img.style.display = 'block'; }
  };
  reader.readAsDataURL(input.files[0]);
}

function handleLogoPreview(input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const mainPreview = document.getElementById('admin_logo_preview');
    const navPreview = document.getElementById('admin_logo_nav_preview');
    if (mainPreview) mainPreview.src = e.target.result;
    if (navPreview) navPreview.src = e.target.result;
    const fileInfo = document.getElementById('admin_logo_filename');
    if (fileInfo) {
      fileInfo.textContent = 'Selected: ' + input.files[0].name;
      fileInfo.style.color = '#7C3AED';
    }
  };
  reader.readAsDataURL(input.files[0]);
}

function previewAvatar(input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const img = document.getElementById('av-preview-img');
    const letter = document.getElementById('av-preview-letter');
    if (img) { img.src = e.target.result; img.style.display = 'block'; }
    if (letter) letter.style.display = 'none';
    const fi = document.querySelector('.file-info');
    if (fi) fi.textContent = 'Selected: ' + input.files[0].name;
  };
  reader.readAsDataURL(input.files[0]);
}

// ============================================================
// 15. ADMIN — TOGGLE NEW PACKAGE
// ============================================================
function toggleNewPkg() {
  const box = document.getElementById('new-pkg-form');
  if (!box) return;
  box.style.display = (box.style.display === 'none' || box.style.display === '') ? 'block' : 'none';
}

// ============================================================
// 16. ADMIN — BROADCAST TARGET
// ============================================================
function pickTarget(type) {
  const box = document.getElementById('specific-user');
  const allBox = document.getElementById('t-all');
  const specBox = document.getElementById('t-spec');
  if (!box) return;
  if (type === 'specific') {
    box.style.display = 'block';
    if (specBox) { specBox.style.borderColor = '#7C3AED'; specBox.style.background = '#EEF2FF'; }
    if (allBox) { allBox.style.borderColor = '#E2E8F0'; allBox.style.background = '#F8FAFC'; }
  } else {
    box.style.display = 'none';
    if (allBox) { allBox.style.borderColor = '#7C3AED'; allBox.style.background = '#EEF2FF'; }
    if (specBox) { specBox.style.borderColor = '#E2E8F0'; specBox.style.background = '#F8FAFC'; }
  }
}

// ============================================================
// 17. COPY HELPERS
// ============================================================
function copyServerUrl() {
  const inp = document.getElementById('server-url-input');
  if (!inp) return;
  inp.select();
  inp.setSelectionRange(0, 99999);
  navigator.clipboard.writeText(inp.value).then(() => {
    showToast('URL copied!', 'success');
  });
}

// ============================================================
// 18. KEYBOARD SHORTCUTS
// ============================================================
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay').forEach(m => {
      if (m.style.display === 'flex') m.style.display = 'none';
    });
    document.querySelectorAll('.dd-wrap.open').forEach(w => w.classList.remove('open'));
  }
});

// ============================================================
// 19. FLASH AUTO-DISMISS
// ============================================================
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(f => {
    f.style.transition = 'all 0.4s ease';
    f.style.opacity = '0';
    f.style.transform = 'translateY(-10px)';
    setTimeout(() => f.remove(), 400);
  });
}, 5000);

// ============================================================
// 20. TRIAL COUNTDOWN (Dashboard)
// ============================================================
function startTrialCountdown(expiresAt) {
  const el = document.getElementById('trial-timer');
  if (!el || !expiresAt) return;
  const target = new Date(expiresAt.replace(' ', 'T') + 'Z').getTime();

  function tick() {
    const now = Date.now();
    const diff = target - now;
    if (diff <= 0) {
      el.textContent = '00:00:00';
      el.classList.add('expired');
      return;
    }
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    el.textContent = String(h).padStart(2, '0') + ':' +
                     String(m).padStart(2, '0') + ':' +
                     String(s).padStart(2, '0');
  }
  tick();
  setInterval(tick, 1000);
}

// ============================================================
// 21. INIT (on page load)
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  // Trial countdown
  const trialEl = document.getElementById('trial-timer');
  if (trialEl && trialEl.dataset.expires) {
    startTrialCountdown(trialEl.dataset.expires);
  }

  // Payment poll (if on checkout page)
  const payPollEl = document.getElementById('payment-poll-order');
  if (payPollEl && payPollEl.dataset.orderId) {
    startPaymentPoll(payPollEl.dataset.orderId);
  }

  // Notification poll
  if (document.getElementById('notif-list')) {
    loadNotifications();
    setInterval(loadNotifications, 30000);
  }
});

// ============================================================
// 22. EXPOSE TO WINDOW (inline handlers)
// ============================================================
window.showToast = showToast;
window.toggleDropdown = toggleDropdown;
window.togglePass = togglePass;
window.loadNotifications = loadNotifications;
window.deleteNotif = deleteNotif;
window.clearAllNotifs = clearAllNotifs;
window.openForgotModal = openForgotModal;
window.closeForgotModal = closeForgotModal;
window.fpSubmitCaptcha = fpSubmitCaptcha;
window.fpSubmitEmail = fpSubmitEmail;
window.fpSubmitReset = fpSubmitReset;
window.serverAction = serverAction;
window.startLogStream = startLogStream;
window.clearLogs = clearLogs;
window.quickCommand = quickCommand;
window.sendTerminalCommand = sendTerminalCommand;
window.clearTerminal = clearTerminal;
window.submitRenew = submitRenew;
window.uploadFile = uploadFile;
window.promptFolder = promptFolder;
window.promptFile = promptFile;
window.openEditor = openEditor;
window.saveEditor = saveEditor;
window.deleteItem = deleteItem;
window.renameItem = renameItem;
window.unzipItem = unzipItem;
window.copyUpiId = copyUpiId;
window.copyText = copyText;
window.selectPayMethod = selectPayMethod;
window.selectManualMethod = selectManualMethod;
window.submitTransactionId = submitTransactionId;
window.openEditUser = openEditUser;
window.togglePermBlock = togglePermBlock;
window.closeEditUser = closeEditUser;
window.previewLogo = previewLogo;
window.handleLogoPreview = handleLogoPreview;
window.previewAvatar = previewAvatar;
window.toggleNewPkg = toggleNewPkg;
window.pickTarget = pickTarget;
window.copyServerUrl = copyServerUrl;