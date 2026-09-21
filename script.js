/* ============================================================
   HOSTX VIP — Main JavaScript
   ============================================================ */

// ============================================================
// LOADER
// ============================================================
(function() {
  function hideLoader() {
    var el = document.getElementById('loader');
    if (el) el.classList.add('hidden');
  }
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(hideLoader, 200);
  } else {
    document.addEventListener('DOMContentLoaded', function() { setTimeout(hideLoader, 200); });
  }
  window.addEventListener('load', function() { setTimeout(hideLoader, 100); });
})();

// ============================================================
// TOAST
// ============================================================
function showToast(msg, type) {
  type = type || 'info';
  var container = document.getElementById('toasts');
  if (!container) return;
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(function() {
    t.style.opacity = '0';
    t.style.transform = 'translateX(20px)';
    t.style.transition = 'all 0.3s ease';
    setTimeout(function() { t.remove(); }, 300);
  }, 3200);
}

// ============================================================
// DROPDOWNS
// ============================================================
function toggleDropdown(event, btn) {
  if (event) event.stopPropagation();
  var wrap = btn.closest('.dd-wrap');
  var isOpen = wrap.classList.contains('open');
  document.querySelectorAll('.dd-wrap.open').forEach(function(w) {
    if (w !== wrap) w.classList.remove('open');
  });
  if (isOpen) {
    wrap.classList.remove('open');
  } else {
    wrap.classList.add('open');
  }
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.dd-wrap')) {
    document.querySelectorAll('.dd-wrap.open').forEach(function(w) {
      w.classList.remove('open');
    });
  }
});

// ============================================================
// PASSWORD TOGGLE
// ============================================================
function togglePass(inputId, btn) {
  var input = document.getElementById(inputId);
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
// NOTIFICATIONS
// ============================================================
function loadNotifications() {
  var list = document.getElementById('notif-list');
  var badge = document.getElementById('notif-badge');
  if (!list) return;
  fetch('/api/notifications')
    .then(function(r) { return r.json(); })
    .then(function(data) {
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
      var html = '';
      data.notifications.forEach(function(n) {
        html += '<div class="notif-item ' + (n.is_read ? '' : 'unread') + '" onclick="deleteNotif(' + n.id + ', event)">' +
          '<div class="notif-item-title"><b>' + escapeHtml(n.title) + '</b><span>' + n.created_at.split('.')[0] + '</span></div>' +
          '<div class="notif-item-msg">' + escapeHtml(n.message) + '</div>' +
          '</div>';
      });
      list.innerHTML = html;
    })
    .catch(function() {
      if (list) list.innerHTML = '<div class="empty-mini">Failed to load.</div>';
    });
}

function deleteNotif(id, event) {
  if (event) event.stopPropagation();
  fetch('/api/notifications/' + id + '/delete', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function() { loadNotifications(); });
}

function clearAllNotifs(event) {
  if (event) event.stopPropagation();
  fetch('/api/notifications/clear-all', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function() {
      showToast('All notifications cleared.', 'success');
      loadNotifications();
    });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Auto load notifications every 30s
if (document.getElementById('notif-list')) {
  loadNotifications();
  setInterval(loadNotifications, 30000);
}

// ============================================================
// GMAIL QUICK LOGIN MODAL
// ============================================================
function openGmailModal() {
  var m = document.getElementById('gmail-modal');
  if (m) {
    m.style.display = 'flex';
    var inp = document.getElementById('gmail-quick-email');
    if (inp) setTimeout(function() { inp.focus(); }, 100);
  }
}

function closeGmailModal() {
  var m = document.getElementById('gmail-modal');
  if (m) m.style.display = 'none';
  var err = document.getElementById('gmail-quick-err');
  if (err) err.style.display = 'none';
}

function submitGmailQuick() {
  var email = (document.getElementById('gmail-quick-email') || {}).value || '';
  var name = (document.getElementById('gmail-quick-name') || {}).value || '';
  var err = document.getElementById('gmail-quick-err');
  var btn = document.getElementById('gmail-quick-btn');

  email = email.trim().toLowerCase();
  name = name.trim();

  if (!email || !email.endsWith('@gmail.com') || email === '@gmail.com') {
    if (err) { err.textContent = 'Please enter a valid Gmail address.'; err.style.display = 'block'; }
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = 'Please wait...'; }

  fetch('/api/quick-gmail-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email, name: name })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message || 'Success!', 'success');
        setTimeout(function() { window.location.href = '/dashboard'; }, 700);
      } else {
        if (err) { err.textContent = data.message || 'Login failed.'; err.style.display = 'block'; }
        if (btn) { btn.disabled = false; btn.textContent = 'Continue'; }
      }
    })
    .catch(function() {
      if (err) { err.textContent = 'Connection error. Try again.'; err.style.display = 'block'; }
      if (btn) { btn.disabled = false; btn.textContent = 'Continue'; }
    });
}

// ============================================================
// FORGOT PASSWORD MODAL
// ============================================================
function openForgotModal() {
  var m = document.getElementById('forgot-modal');
  if (m) {
    m.style.display = 'flex';
    showFpStep(1);
    loadCaptcha();
  }
}

function closeForgotModal() {
  var m = document.getElementById('forgot-modal');
  if (m) m.style.display = 'none';
}

function showFpStep(step) {
  var s1 = document.getElementById('fp-step1');
  var s2 = document.getElementById('fp-step2');
  var s3 = document.getElementById('fp-step3');
  if (s1) s1.style.display = step === 1 ? 'block' : 'none';
  if (s2) s2.style.display = step === 2 ? 'block' : 'none';
  if (s3) s3.style.display = step === 3 ? 'block' : 'none';

  var b1 = document.getElementById('sb1');
  var b2 = document.getElementById('sb2');
  var b3 = document.getElementById('sb3');
  if (b1) b1.className = 'stepb' + (step >= 1 ? ' active' : '') + (step > 1 ? ' done' : '');
  if (b2) b2.className = 'stepb' + (step >= 2 ? ' active' : '') + (step > 2 ? ' done' : '');
  if (b3) b3.className = 'stepb' + (step >= 3 ? ' active' : '');
}

function loadCaptcha() {
  var box = document.getElementById('fp-captcha');
  if (!box) return;
  box.textContent = 'Loading...';
  fetch('/api/forgot-password/captcha')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      box.textContent = data.question || 'Error';
      var ans = document.getElementById('fp-captcha-answer');
      if (ans) ans.value = '';
    })
    .catch(function() { box.textContent = 'Error loading'; });
}

function fpSubmitCaptcha() {
  var ans = (document.getElementById('fp-captcha-answer') || {}).value || '';
  var err = document.getElementById('fp-cap-err');
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
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) { showFpStep(2); }
      else {
        if (err) { err.textContent = data.message || 'Incorrect.'; err.style.display = 'block'; }
        loadCaptcha();
      }
    })
    .catch(function() {
      if (err) { err.textContent = 'Connection error.'; err.style.display = 'block'; }
    });
}

function fpSubmitEmail() {
  var email = (document.getElementById('fp-email') || {}).value || '';
  var err = document.getElementById('fp-email-err');
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
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) { showFpStep(3); }
      else {
        if (err) { err.textContent = data.message || 'Not registered.'; err.style.display = 'block'; }
      }
    })
    .catch(function() {
      if (err) { err.textContent = 'Connection error.'; err.style.display = 'block'; }
    });
}

function fpSubmitReset() {
  var pw = (document.getElementById('fp-new-pass') || {}).value || '';
  var cp = (document.getElementById('fp-conf-pass') || {}).value || '';
  var err = document.getElementById('fp-pw-err');
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
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast('Password updated! Please sign in.', 'success');
        closeForgotModal();
      } else {
        if (err) { err.textContent = data.message || 'Error.'; err.style.display = 'block'; }
      }
    })
    .catch(function() {
      if (err) { err.textContent = 'Connection error.'; err.style.display = 'block'; }
    });
}

// ============================================================
// DAILY COIN CLAIM
// ============================================================
function claimDaily() {
  var btn = document.getElementById('claim-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Claiming...'; }
  fetch('/api/coins/claim-daily', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message, 'success');
        var bal = document.getElementById('coin-bal');
        if (bal) bal.textContent = data.new_balance;
        var headerCoins = document.querySelectorAll('.coin-pill b, .user-coin-val');
        headerCoins.forEach(function(el) { el.textContent = data.new_balance; });
        if (btn) {
          btn.outerHTML = '<div class="claim-disabled">Next claim at 12:00 AM</div>';
        }
      } else {
        showToast(data.message || 'Claim failed.', 'danger');
        if (btn) { btn.disabled = false; btn.textContent = '🎁 Claim'; }
      }
    })
    .catch(function() {
      showToast('Connection error.', 'danger');
      if (btn) { btn.disabled = false; btn.textContent = '🎁 Claim'; }
    });
}

// ============================================================
// SERVER ACTIONS (start/stop/restart)
// ============================================================
function serverAction(serverId, action) {
  var btn = document.getElementById('btn-' + action);
  var originalText = '';
  if (btn) {
    originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '⏳ Please wait...';
  }

  fetch('/api/servers/' + serverId + '/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: action })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message || 'Success!', 'success');
        updateStatusBadge(data.status, data.pid);
        updatePidBadge(data.pid);
        // Reload after short delay to reflect new state
        setTimeout(function() { window.location.reload(); }, 900);
      } else {
        // Handle special errors
        if (data.no_entry_file || data.redirect_url) {
          var modal = document.getElementById('no-entry-modal');
          if (modal) {
            modal.style.display = 'flex';
          } else if (data.redirect_url) {
            showToast(data.message || 'Entry file missing.', 'warning');
            setTimeout(function() { window.location.href = data.redirect_url; }, 1200);
          }
        } else if (data.package_required && data.missing_packages) {
          var names = data.missing_packages.map(function(p) { return p.name; }).join(', ');
          showToast('Missing packages: ' + names + '. Install them first.', 'warning');
        } else {
          showToast(data.message || 'Action failed.', 'danger');
        }
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      }
    })
    .catch(function(err) {
      showToast('Network error: ' + err.message, 'danger');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });
}

function updateStatusBadge(status, pid) {
  var badge = document.getElementById('status-badge');
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
  var badge = document.getElementById('pid-badge');
  if (!badge) return;
  if (pid && pid > 0) {
    badge.textContent = 'PID: ' + pid;
    badge.className = 'pid-badge pid-on';
  } else {
    badge.textContent = 'PID: Offline';
    badge.className = 'pid-badge';
  }
  var dot = document.getElementById('status-dot');
  var txt = document.getElementById('status-text');
  if (pid && pid > 0) {
    if (dot) dot.classList.add('on');
    if (txt) { txt.classList.add('on'); txt.textContent = 'Running'; }
  } else {
    if (dot) dot.classList.remove('on');
    if (txt) { txt.classList.remove('on'); txt.textContent = 'Offline'; }
  }
}

// ============================================================
// LIVE LOG STREAMING
// ============================================================
var logStreamInterval = null;

function startLogStream(serverId, startTime) {
  var term = document.getElementById('terminal');
  if (!term) return;
  var tick = document.getElementById('uptime-tick');

  function fetchLogs() {
    fetch('/api/servers/' + serverId + '/logs')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        // Update terminal
        if (data.raw_logs) {
          var lines = data.raw_logs.split('\n');
          var html = '';
          lines.slice(-200).forEach(function(line) {
            if (!line.trim()) return;
            var cls = 'log-info';
            var lower = line.toLowerCase();
            if (lower.includes('error') || lower.includes('traceback') || lower.includes('exception')) cls = 'log-error';
            else if (lower.includes('warning') || lower.includes('warn')) cls = 'log-warning';
            else if (lower.includes('success') || lower.includes('started') || lower.includes('running')) cls = 'log-success';
            else if (lower.includes('stopping') || lower.includes('stopped')) cls = 'log-running';
            html += '<div class="log-line ' + cls + '">' + escapeHtml(line) + '</div>';
          });
          term.innerHTML = html || '<div class="log-line log-info">[INFO] No logs yet. Start the server to see output.</div>';
          term.scrollTop = term.scrollHeight;
        }

        // Update status
        updatePidBadge(data.pid);
        updateStatusBadge(data.status, data.pid);

        // Update uptime
        if (data.status === 'running' && data.start_time > 0) {
          var secs = Math.floor(Date.now() / 1000 - data.start_time);
          var h = Math.floor(secs / 3600);
          var m = Math.floor((secs % 3600) / 60);
          var s = secs % 60;
          if (tick) {
            tick.textContent = String(h).padStart(2, '0') + ':' +
              String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
          }
        } else {
          if (tick) tick.textContent = '00:00:00';
        }
      })
      .catch(function() {});
  }

  fetchLogs();
  if (logStreamInterval) clearInterval(logStreamInterval);
  logStreamInterval = setInterval(fetchLogs, 3000);
}

function clearLogs(serverId) {
  if (!confirm('Clear all logs for this server?')) return;
  fetch('/api/servers/' + serverId + '/logs/clear', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast('Logs cleared.', 'success');
        var term = document.getElementById('terminal');
        if (term) term.innerHTML = '<div class="log-line log-info">[INFO] Logs cleared.</div>';
      } else {
        showToast(data.message || 'Failed.', 'danger');
      }
    });
}

// ============================================================
// RENEW SERVER
// ============================================================
function submitRenew(serverId, isExpired) {
  var selector = isExpired ? 'input[name="renew_pkg_exp"]:checked' : 'input[name="renew_pkg"]:checked';
  var selected = document.querySelector(selector);
  if (!selected) {
    showToast('Please select a package.', 'warning');
    return;
  }

  var btn = document.querySelector('#renew-modal .btn-primary, .modal-card .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = 'Processing...'; }

  fetch('/api/servers/' + serverId + '/renew', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ package_id: selected.value })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message || 'Renewed!', 'success');
        setTimeout(function() { window.location.reload(); }, 900);
      } else {
        showToast(data.message || 'Renewal failed.', 'danger');
        if (btn) { btn.disabled = false; btn.textContent = 'Confirm Extension'; }
      }
    })
    .catch(function() {
      showToast('Network error.', 'danger');
      if (btn) { btn.disabled = false; btn.textContent = 'Confirm Extension'; }
    });
}

// ============================================================
// FILE MANAGER
// ============================================================
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  var k = 1024;
  var sizes = ['B', 'KB', 'MB', 'GB'];
  var i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function uploadFile(serverId, input, isZip) {
  if (!input.files || input.files.length === 0) return;

  var files = input.files;
  var fd = new FormData();
  fd.append('path', window.location.search ? new URLSearchParams(window.location.search).get('path') || '' : '');
  for (var i = 0; i < files.length; i++) {
    fd.append('files', files[i]);
  }

  // Show modal
  var modal = document.getElementById('up-modal');
  var title = document.getElementById('up-title');
  var icon = document.getElementById('up-icon');
  var sub = document.getElementById('up-sub');
  var bar = document.getElementById('up-bar');
  var pct = document.getElementById('up-pct');
  var size = document.getElementById('up-size');

  if (modal) modal.style.display = 'flex';
  if (title) title.textContent = isZip ? 'Uploading & Extracting ZIP...' : 'Uploading Files...';
  if (icon) icon.textContent = isZip ? '📦' : '📤';
  if (sub) sub.textContent = 'Please wait.';
  if (bar) bar.style.width = '0%';
  if (pct) pct.textContent = '0%';
  if (size) size.textContent = '0 B / 0 B';

  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/servers/' + serverId + '/files/upload', true);

  xhr.upload.onprogress = function(e) {
    if (e.lengthComputable) {
      var percent = Math.round((e.loaded / e.total) * 100);
      if (bar) bar.style.width = percent + '%';
      if (pct) pct.textContent = percent + '%';
      if (size) size.textContent = formatBytes(e.loaded) + ' / ' + formatBytes(e.total);
      if (sub && percent >= 100) sub.textContent = 'Processing on server...';
    }
  };

  xhr.onload = function() {
    if (modal) modal.style.display = 'none';
    try {
      var data = JSON.parse(xhr.responseText);
      if (data.success) {
        showToast(data.message || 'Uploaded!', 'success');
        setTimeout(function() { window.location.reload(); }, 700);
      } else {
        showToast(data.message || 'Upload failed.', 'danger');
      }
    } catch (err) {
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
  var name = prompt('New folder name:');
  if (!name) return;
  var fd = new FormData();
  fd.append('path', window.location.search ? new URLSearchParams(window.location.search).get('path') || '' : '');
  fd.append('folder_name', name);
  fetch('/api/servers/' + serverId + '/files/create-folder', { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message, 'success');
        setTimeout(function() { window.location.reload(); }, 600);
      } else {
        showToast(data.message, 'danger');
      }
    });
}

function promptFile(serverId) {
  var name = prompt('New file name (e.g. config.py):');
  if (!name) return;
  var fd = new FormData();
  fd.append('path', window.location.search ? new URLSearchParams(window.location.search).get('path') || '' : '');
  fd.append('file_name', name);
  fetch('/api/servers/' + serverId + '/files/create-file', { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message, 'success');
        setTimeout(function() { window.location.reload(); }, 600);
      } else {
        showToast(data.message, 'danger');
      }
    });
}

function openEditor(serverId, path) {
  var modal = document.getElementById('editor-modal');
  var nameEl = document.getElementById('ed-file');
  var pathEl = document.getElementById('ed-path');
  var contentEl = document.getElementById('ed-content');
  if (!modal) return;

  if (nameEl) nameEl.textContent = path.split('/').pop();
  if (pathEl) pathEl.value = path;
  if (contentEl) contentEl.value = 'Loading...';

  modal.style.display = 'flex';

  fetch('/api/servers/' + serverId + '/files/read?path=' + encodeURIComponent(path))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        if (contentEl) contentEl.value = data.content || '';
      } else {
        if (contentEl) contentEl.value = '// Error: ' + (data.message || 'Could not load.');
      }
    })
    .catch(function() {
      if (contentEl) contentEl.value = '// Failed to load file.';
    });
}

function saveEditor(serverId) {
  var pathEl = document.getElementById('ed-path');
  var contentEl = document.getElementById('ed-content');
  var btn = document.getElementById('ed-save');
  if (!pathEl || !contentEl) return;

  if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }

  fetch('/api/servers/' + serverId + '/files/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: pathEl.value, content: contentEl.value })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast('File saved!', 'success');
        var m = document.getElementById('editor-modal');
        if (m) m.style.display = 'none';
      } else {
        showToast(data.message || 'Save failed.', 'danger');
      }
      if (btn) { btn.disabled = false; btn.textContent = '💾 Save'; }
    })
    .catch(function() {
      showToast('Network error.', 'danger');
      if (btn) { btn.disabled = false; btn.textContent = '💾 Save'; }
    });
}

function deleteItem(serverId, path) {
  if (!confirm('Delete "' + path + '"? This cannot be undone.')) return;
  fetch('/api/servers/' + serverId + '/files/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: path })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast('Deleted.', 'success');
        setTimeout(function() { window.location.reload(); }, 600);
      } else {
        showToast(data.message, 'danger');
      }
    });
}

function renameItem(serverId, path) {
  var oldName = path.split('/').pop();
  var newName = prompt('Rename "' + oldName + '" to:', oldName);
  if (!newName || newName === oldName) return;
  fetch('/api/servers/' + serverId + '/files/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_path: path, new_name: newName })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message, 'success');
        setTimeout(function() { window.location.reload(); }, 600);
      } else {
        showToast(data.message, 'danger');
      }
    });
}

function unzipItem(serverId, path) {
  if (!confirm('Extract "' + path + '"?')) return;
  fetch('/api/servers/' + serverId + '/files/unzip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: path })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        showToast(data.message || 'Extracted!', 'success');
        setTimeout(function() { window.location.reload(); }, 900);
      } else {
        showToast(data.message, 'danger');
      }
    });
}

// ============================================================
// AVATAR PREVIEW (Account page)
// ============================================================
function previewAvatar(input) {
  if (!input.files || !input.files[0]) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    var img = document.getElementById('av-preview-img');
    var letter = document.getElementById('av-preview-letter');
    if (img) {
      img.src = e.target.result;
      img.style.display = 'block';
    }
    if (letter) letter.style.display = 'none';
    var fi = document.querySelector('.file-info');
    if (fi) fi.textContent = 'Selected: ' + input.files[0].name;
  };
  reader.readAsDataURL(input.files[0]);
}

// ============================================================
// ADMIN — EDIT USER MODAL
// ============================================================
function openEditUser(id, name, username, email, bio, coins, role, status, perms, isSuper) {
  var modal = document.getElementById('edit-user-modal');
  if (!modal) return;

  var form = document.getElementById('edit-user-form');
  if (form) form.action = '/admin/users/' + id + '/update';

  var nameEl = document.getElementById('eu_name'); if (nameEl) nameEl.value = name;
  var userEl = document.getElementById('eu_user'); if (userEl) userEl.value = username;
  var emailEl = document.getElementById('eu_email'); if (emailEl) emailEl.value = email;
  var bioEl = document.getElementById('eu_bio'); if (bioEl) bioEl.value = bio || '';
  var coinsEl = document.getElementById('eu_coins'); if (coinsEl) coinsEl.value = coins;
  var passEl = document.getElementById('eu_pass'); if (passEl) passEl.value = '';

  var roleEl = document.getElementById('eu_role');
  if (roleEl) {
    roleEl.value = isSuper ? 'super_admin' : role;
    togglePermBlock(roleEl.value);
  }

  var statusEl = document.getElementById('eu_status');
  if (statusEl) statusEl.value = status;

  // Permissions checkboxes
  if (perms) {
    var list = perms === 'all' ? ['manage_users','manage_coins','manage_files','manage_settings','manage_announcements','manage_broadcasts','view_logs'] : perms.split(',');
    ['manage_users','manage_coins','manage_files','manage_settings','manage_announcements','manage_broadcasts','view_logs'].forEach(function(p) {
      var el = document.getElementById('p_' + p.replace('manage_', '').replace('view_', ''));
      if (el) el.checked = list.indexOf(p) !== -1;
    });
  }

  modal.style.display = 'flex';
}

function togglePermBlock(roleVal) {
  var block = document.getElementById('perm-block');
  if (block) {
    block.style.display = (roleVal === 'admin') ? 'block' : 'none';
  }
}

function closeEditUser() {
  var m = document.getElementById('edit-user-modal');
  if (m) m.style.display = 'none';
}

// ============================================================
// ADMIN — PREVIEW FILE
// ============================================================
function adminPreview(serverId, filename, serverName) {
  var modal = document.getElementById('admin-preview-modal');
  var nameEl = document.getElementById('ap-file');
  var subEl = document.getElementById('ap-sub');
  var contentEl = document.getElementById('ap-content');
  var dlEl = document.getElementById('ap-dl');
  if (!modal) return;

  if (nameEl) nameEl.textContent = filename;
  if (subEl) subEl.textContent = 'Server: ' + serverName + ' (# ' + serverId + ')';
  if (contentEl) contentEl.textContent = 'Loading...';
  if (dlEl) dlEl.href = '/admin/servers/' + serverId + '/files/download?path=' + encodeURIComponent(filename);

  modal.style.display = 'flex';

  fetch('/admin/api/servers/' + serverId + '/files/read?path=' + encodeURIComponent(filename))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.success) {
        if (contentEl) contentEl.textContent = data.content || '';
      } else {
        if (contentEl) contentEl.textContent = 'Error: ' + (data.message || 'Could not load.');
      }
    })
    .catch(function() {
      if (contentEl) contentEl.textContent = 'Failed to load. Use direct download.';
    });
}

// ============================================================
// ADMIN — BROADCAST TARGET
// ============================================================
function pickTarget(type) {
  var box = document.getElementById('specific-user');
  var allBox = document.getElementById('t-all');
  var specBox = document.getElementById('t-spec');
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
// ADMIN — LOGO PREVIEW
// ============================================================
function previewLogo(input) {
  if (!input.files || !input.files[0]) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    var img = document.getElementById('logo-preview');
    if (img) {
      img.src = e.target.result;
      img.style.display = 'block';
    }
  };
  reader.readAsDataURL(input.files[0]);
}

// ============================================================
// ADMIN — NEW PACKAGE TOGGLE
// ============================================================
function toggleNewPkg() {
  var box = document.getElementById('new-pkg-form');
  if (!box) return;
  box.style.display = (box.style.display === 'none' || box.style.display === '') ? 'block' : 'none';
}

// ============================================================
// KEYBOARD SHORTCUTS
// ============================================================
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay').forEach(function(m) {
      if (m.style.display === 'flex') m.style.display = 'none';
    });
    document.querySelectorAll('.dd-wrap.open').forEach(function(w) {
      w.classList.remove('open');
    });
  }
});

// ============================================================
// AUTO-DISMISS FLASH MESSAGES
// ============================================================
setTimeout(function() {
  document.querySelectorAll('.flash').forEach(function(f) {
    f.style.transition = 'all 0.4s ease';
    f.style.opacity = '0';
    f.style.transform = 'translateY(-10px)';
    setTimeout(function() { f.remove(); }, 400);
  });
}, 5000);