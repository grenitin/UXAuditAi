let progressValue    = 0;
let progressInterval;
let currentPage      = 1;
const itemsPerPage   = 3;
let livePopupRef     = null; // Reference to the managed live site popup

// Mock database for the "History" dashboard
let mockHistory = JSON.parse(localStorage.getItem('uxAuditHistory')) || [];

function saveHistory() {
  localStorage.setItem('uxAuditHistory', JSON.stringify(mockHistory));
}

function updatePlaceholder() {
  const provider = document.getElementById('providerSelect').value;
  const apiInput = document.getElementById('apiKeyInput');
  const labels = {
    'gemini': 'Enter Gemini API Key',
    'openai': 'Enter OpenAI API Key',
    'anthropic': 'Enter Anthropic API Key'
  };
  apiInput.placeholder = labels[provider] || 'Enter API Key';
  
  // Load saved key if it exists for this provider
  const savedKey = localStorage.getItem(`savedKey_${provider}`);
  if (savedKey) {
    apiInput.value = savedKey;
  } else {
    apiInput.value = '';
  }
}

function fillUrl(url) {
  console.log("Filling URL preset:", url);
  const input = document.getElementById('urlInput');
  if (input) {
    input.value = url;
    // Dispatch input event to trigger any listeners
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
    
    // Smooth scroll to the input if it's not fully visible
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function resetUI() {
  document.getElementById('statusCard').style.display = 'none';
  document.getElementById('resultPanel').style.display = 'none';
  document.getElementById('errorCard').style.display   = 'none';
  
  const historyCard = document.getElementById('historyCard');
  if (historyCard) historyCard.style.display = 'none';

  document.getElementById('inputCard').style.display   = 'block';
  document.getElementById('urlInput').value = ''; // Clear URL as requested
  
  // Keep API Key populated
  updatePlaceholder();

  // Sync history counts and list state
  renderHistory();

  document.body.classList.remove('audit-running');
  document.documentElement.classList.remove('no-scroll');
  updateButtonState(false); // Reset to "Run Audit"
  progressValue = 0;
  document.getElementById('progressBar').style.width = '0%';
  clearInterval(progressInterval);
}

function pushTerminalLine(msg) {
  const terminal = document.getElementById('terminal');
  const line      = document.getElementById('statusMsg');
  line.textContent = msg;

  // Also append a history line
  const hist = document.createElement('div');
  hist.className   = 'terminal-line';
  hist.style.opacity = '0.4';
  hist.style.fontSize = '0.72rem';
  hist.textContent = msg;
  terminal.insertBefore(hist, line);
  terminal.scrollTop = terminal.scrollHeight;
}

function tickProgress(target) {
  clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    if (progressValue < target) {
      progressValue += 0.5;
      document.getElementById('progressBar').style.width = progressValue + '%';
    }
  }, 80);
}

async function startAudit() {
  const urlInput = document.getElementById('urlInput');
  const apiKeyInput = document.getElementById('apiKeyInput');
  const providerSelect = document.getElementById('providerSelect');
  
  const url      = urlInput.value.trim();
  const apiKey   = apiKeyInput.value.trim();
  const provider = providerSelect.value;

  // Automatically remember the key for this provider
  if (apiKey) {
    localStorage.setItem(`savedKey_${provider}`, apiKey);
  }

  if (!apiKey) {
    apiKeyInput.focus();
    showApiError("Please enter your Gemini API Key. You can get one from Google AI Studio.");
    return;
  }

  if (!url) {
    urlInput.focus();
    urlInput.style.borderColor = '#ef4444';
    setTimeout(() => urlInput.style.borderColor = '', 1200);
    return;
  }

  // Lock UI
  document.body.classList.add('audit-running');
  document.documentElement.classList.add('no-scroll');
  updateButtonState(true);
  document.getElementById('resultPanel').style.display = 'none';
  document.getElementById('errorCard').style.display   = 'none';
  document.getElementById('historyCard').style.display = 'none'; // Hide history during run

  // Transition UI to Monitoring Mode
  document.getElementById('inputCard').style.display = 'none'; // Hide the input panel
  const statusPanel = document.getElementById('statusCard');
  statusPanel.style.display = 'flex';
  document.getElementById('statusBrand').textContent = url.replace('https://', '').replace('http://', '').split('/')[0];

  // Extract brand name
  try {
    const hostname = new URL(url.startsWith('http') ? url : 'https://' + url).hostname;
    document.getElementById('statusBrand').textContent = hostname.replace('www.', '');
  } catch (_) {}

  // Kick progress to 5%
  tickProgress(5);

  // POST to backend
  let taskId;
  try {
    const res  = await fetch('/run_audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, api_key: apiKey, provider: provider })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || 'Server error');
    taskId = data.task_id;
  } catch (err) {
    showError('Failed to start audit: ' + err.message);
    return;
  }

  // Define brand/hostname here to ensure it's available in the completion closure
  let brandName = 'Latest Audit';
  try {
    const parsedUrl = new URL(url.startsWith('http') ? url : 'https://' + url);
    brandName = parsedUrl.hostname.replace('www.', '');
  } catch (_) {}

  // SSE — stream live status
  const evtSource = new EventSource(`/status/${taskId}`);

  // Reset all stages to pending for the live run
  const stages = ['handshake', 'discovery', 'synthesis', 'intelligence', 'report', 'sync'];
  stages.forEach(s => updateTaskStatus(s, 'pending'));
  
  let currentTaskKey = null;

  evtSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    
    // Update terminal and raw status
    pushTerminalLine(data.status);

    // Dynamic Pipeline Tracking
    if (data.current_task && data.current_task !== currentTaskKey) {
        
        // Mark all tasks strictly prior to current as 'done' safely catching up missed SSE pulses
        const currentIdx = stages.indexOf(data.current_task);
        if (currentIdx > 0) {
            for (let i = 0; i < currentIdx; i++) {
                updateTaskStatus(stages[i], 'done');
            }
        }
        
        // Mark new task as active
        currentTaskKey = data.current_task;
        updateTaskStatus(currentTaskKey, 'active');
        
        // Map progress based on task
        const taskProgress = {
            'handshake': 10,
            'discovery': 20,
            'synthesis': 45,
            'intelligence': 75,
            'report': 90,
            'sync': 98
        };
        if (taskProgress[currentTaskKey]) tickProgress(taskProgress[currentTaskKey]);

        // Portal auto-open disabled per user request. 
        // Can be triggered manually via UI if needed.
        if (currentTaskKey === 'discovery') {
          const vBtn = document.getElementById('viewVisionBtn');
          if (vBtn) vBtn.style.display = 'block';
        }
        // if (currentTaskKey === 'discovery') { openPortal(); }

        // Live Vision Sync
        if (data.visual_update) {
          refreshLiveSnapshot();
        }
    }

    if (data.complete) {
      evtSource.close();
      clearInterval(progressInterval);
      closePortal(); // Auto-close HUD when audit finishes
      
      // Even if there was a minor sync error, we check if we have results to show
      const isSyncErrorOnly = data.error && data.current_task === 'sync';
      
      if (data.error && !isSyncErrorOnly) {
        if (currentTaskKey) updateTaskStatus(currentTaskKey, 'error');
        
        // Check if it's an API Key error
        const errorLower = data.error.toLowerCase();
        if (errorLower.includes('api key') || errorLower.includes('permission_denied') || errorLower.includes('handshake failed')) {
            showApiError("The provided Gemini API Key is invalid or restricted. Please check your key permissions in Google AI Studio.");
        } else {
            showError(data.error);
        }
      } else {
        // Finalize all remaining stages
        stages.forEach(s => {
          if (s === 'sync' && isSyncErrorOnly) {
             updateTaskStatus(s, 'error'); // Mark sync as failed specifically
          } else {
             updateTaskStatus(s, 'done');
          }
        });
        
        document.getElementById('progressBar').style.width = '100%';
        document.getElementById('statusMsg').textContent = isSyncErrorOnly ? 'Audit Done (Sync Failed)' : 'Audit Completed Successfully';

        // Automatically open the detail modal and save to history
        setTimeout(async () => {
          let issueCount = 0;
          let resultData = null;
          try {
            const res = await fetch(`/results/${taskId}`);
            resultData = await res.json();
            if (resultData.issues) issueCount = resultData.issues.length;
          } catch (e) {
            console.error("Failed to fetch results for history:", e);
          }

          // Remove any existing duplicate for the same URL or Brand to keep only the latest
          mockHistory = mockHistory.filter(item => item.url !== url && item.brand !== brandName);

          mockHistory.unshift({
            id: taskId,
            brand: brandName,
            date: new Date().toLocaleString(),
            url: url,
            issues: issueCount
          });
          
          // LEAD ARCHITECT FIX: Save full report to LocalStorage to survive server restarts on Free Tier
          if (resultData) {
            localStorage.setItem(`audit_report_${taskId}`, JSON.stringify(resultData));
          }

          saveHistory();

          document.getElementById('statusCard').style.display = 'none';
          document.getElementById('runBtn').disabled = false;
          document.getElementById('btnText').textContent = 'Run Audit';
          document.getElementById('btnArrow').textContent = '→';
          
          renderHistory(); // Refresh history view
          window.location.href = `/report/${taskId}`;
          
          // If it was a sync error, notify the user but stay in the results view
          if (isSyncErrorOnly) {
            console.warn("Audit local results displayed, but cloud sync failed:", data.error);
          }
        }, 2200);
      }
    }
  };

  evtSource.onerror = (e) => {
    console.error('SSE Error:', e);
    evtSource.close();
    clearInterval(progressInterval);
    if (progressValue < 95) {
      showError('The audit process was interrupted. This often happens with heavy prototypes during the vision phase. Try refreshing the page and running the audit again.');
    }
  };
}

function updateTaskStatus(taskId, status) {
  const item = document.getElementById(`task-${taskId}`);
  if (!item) return;

  const iconEl = item.querySelector('.task-icon');
  const statusEl = item.querySelector('.task-status');

  item.classList.remove('active', 'done', 'error');
  
  if (status === 'active') {
    item.classList.add('active');
    iconEl.textContent = '◌';
    statusEl.textContent = 'Ongoing';
    
    // Smooth auto-scroll pipeline list to the active item
    const pipelineList = document.getElementById('pipelineList');
    if (pipelineList) {
      pipelineList.scrollTo({
        top: item.offsetTop - pipelineList.offsetTop - 20,
        behavior: 'smooth'
      });
    }
  } else if (status === 'done') {
    item.classList.add('done');
    iconEl.textContent = '✓';
    statusEl.textContent = 'Completed';
  } else if (status === 'error') {
    item.classList.add('error');
    iconEl.textContent = '×';
    statusEl.textContent = 'Blocked';
  } else {
    iconEl.textContent = '◌';
    statusEl.textContent = 'Pending';
  }
}



async function fetchResults(auditUrl) {
  // Results are in the CSV — fetch from a results endpoint
  try {
    const res  = await fetch('/results');
    const data = await res.json();

    if (!data.issues || data.issues.length === 0) {
      showError('Audit completed but no issues were returned. Check that GEMINI_API_KEY is set.');
      return;
    }

    document.getElementById('statusCard').style.display  = 'none';
    document.getElementById('resultPanel').style.display = 'block';
    document.getElementById('resultSummary').textContent =
      `${data.issues.length} usability issues found across ${data.pages} pages — sorted by severity.`;

    const grid = document.getElementById('resultGrid');
    grid.innerHTML = '';

    data.issues.forEach((issue, i) => {
      const cogLoad = (issue['Cognitive Load'] || 'Medium').toLowerCase();
      const sev     = issue['Severity'] || '?';

      const card = document.createElement('div');
      card.className = 'issue-card';
      card.style.animationDelay = (i * 0.06) + 's';
      card.innerHTML = `
        <div class="issue-meta">
          <span class="tag tag-heuristic">${issue['Heuristic'] || 'Heuristic'}</span>
          <span class="tag tag-${cogLoad}">${issue['Cognitive Load'] || 'Medium'} Load</span>
          <span class="tag tag-sev">Sev ${sev}</span>
          <span class="tag tag-sev">${issue['Priority'] || 'P2'}</span>
          <span class="issue-page">${issue['Page Name'] || ''}</span>
        </div>
        <div class="issue-title">${issue['Issue Description'] || ''}</div>
        <div class="issue-desc">
          <strong style="color:#a0a0b8;">Behavioral:</strong> ${issue['Behavioral Insight'] || '—'}<br/>
          <strong style="color:#a0a0b8;">Attitudinal:</strong> ${issue['Attitudinal Insight'] || '—'}
        </div>
        <div class="issue-rec">${issue['Recommendation'] || '—'}</div>
      `;
      grid.appendChild(card);
    });

  } catch (err) {
    showError('Audit finished but could not load results: ' + err.message);
  }
}

function cancelAudit() {
  if (confirm("Are you sure you want to cancel the current audit?")) {
    closePortal();
    resetUI();
  }
}

// ── New Dynamic Button Controller ──
let isAuditRunning = false;
function handleAction() {
  if (isAuditRunning) {
    cancelAudit();
  } else {
    startAudit();
  }
}

function updateButtonState(running) {
  isAuditRunning = running;
  const btn = document.getElementById('runBtn');
  const text = document.getElementById('btnText');
  const arrow = document.getElementById('btnArrow');

  if (running) {
    btn.classList.add('btn-running');
    text.textContent = 'Cancel Audit';
    if (arrow) arrow.style.display = 'none';
    btn.disabled = false; // Must be enabled to allow Cancel click
  } else {
    btn.classList.remove('btn-running');
    text.textContent = 'Run Audit';
    if (arrow) arrow.style.display = 'inline';
    btn.disabled = false;
  }
}

// ── Portal Management (In-Tab HUD) ──
let cursorInterval = null;

function openPortal() {
  const portal = document.getElementById('viewportPortal');
  portal.style.display = 'flex';
  
  // Re-center if it hasn't been dragged
  if (!portal.classList.contains('is-dragged')) {
    portal.style.top = '50%';
    portal.style.left = '50%';
    portal.style.transform = 'translate(-50%, -50%)';
  }

  initDraggable(portal);
  startCursorSimulation();
}

function closePortal() {
  const portal = document.getElementById('viewportPortal');
  portal.style.display = 'none';
  stopCursorSimulation();
}

function startCursorSimulation() {
  const cursor = document.getElementById('agentCursor');
  const container = document.getElementById('portalContent');
  if (!cursor || !container) return;
  
  cursor.style.display = 'block';
  
  function move() {
    const maxX = container.clientWidth - 50;
    const maxY = container.clientHeight - 50;
    const x = Math.random() * maxX;
    const y = Math.random() * maxY;
    
    cursor.style.left = `${x}px`;
    cursor.style.top = `${y}px`;
    
    // Vary the speed slightly
    const nextWait = 800 + Math.random() * 1500;
    cursorInterval = setTimeout(move, nextWait);
  }
  
  move();
}

function stopCursorSimulation() {
  if (cursorInterval) {
    clearTimeout(cursorInterval);
    cursorInterval = null;
  }
}

function refreshLiveSnapshot() {
  const img = document.getElementById('liveSnapshot');
  if (img) {
    // Cache-busting to ensure browser loads the fresh buffer from disk
    img.src = '/static/live_audit.png?t=' + Date.now();
  }
}

function initDraggable(el) {
  const header = el.querySelector('.portal-header');
  let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

  header.onmousedown = dragMouseDown;

  function dragMouseDown(e) {
    e.preventDefault();
    pos3 = e.clientX;
    pos4 = e.clientY;
    document.onmouseup = closeDragElement;
    document.onmousemove = elementDrag;
  }

  function elementDrag(e) {
    e.preventDefault();
    pos1 = pos3 - e.clientX;
    pos2 = pos4 - e.clientY;
    pos3 = e.clientX;
    pos4 = e.clientY;
    
    // Remove centering transform on first drag
    el.style.transform = 'none';
    el.classList.add('is-dragged');

    // Set new position while preventing it from going off-screen
    const newTop = el.offsetTop - pos2;
    const newLeft = el.offsetLeft - pos1;
    
    el.style.top = newTop + "px";
    el.style.left = newLeft + "px";
    el.style.bottom = 'auto';
    el.style.right = 'auto';
  }

  function closeDragElement() {
    document.onmouseup = null;
    document.onmousemove = null;
  }
}

// ── Dashboard & Modal Logic ──

function renderHistory() {
  const container = document.getElementById('historyList');
  const countEl = document.getElementById('historyCount');
  const paginationEl = document.getElementById('paginationContainer');
  
  if (!container) return;
  
  const historyCard = document.getElementById('historyCard');
  if (mockHistory.length === 0) {
    if (historyCard) historyCard.style.display = 'none';
    return;
  }
  if (historyCard) historyCard.style.display = 'block';

  countEl.textContent = mockHistory.length;
  container.innerHTML = '';
  
  // Pagination Logic
  let start = (currentPage - 1) * itemsPerPage;
  if (start >= mockHistory.length && mockHistory.length > 0) {
    currentPage = Math.max(1, Math.ceil(mockHistory.length / itemsPerPage));
    start = (currentPage - 1) * itemsPerPage;
  }
  const end = start + itemsPerPage;
  const pageItems = mockHistory.slice(start, end);

  pageItems.forEach((item, i) => {
    let domain = 'google.com';
    try {
      if (item.url) {
        // Handle cases where URL might be missing protocol
        const fullUrl = item.url.startsWith('http') ? item.url : 'https://' + item.url;
        domain = new URL(fullUrl).hostname;
      }
    } catch (e) {
      console.warn("Invalid URL in history:", item.url);
    }
    
    const logoUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
    const cleanUrl = item.url ? item.url.replace('https://','').replace('http://','').replace('www.','') : 'N/A';
    
    const el = document.createElement('div');
    el.className = 'history-item';
    el.style.animation = `fadeUp 0.4s ease forwards ${i * 0.05}s`;
    el.innerHTML = `
      <div class="history-main">
        <div class="brand-logo-wrap">
          <img src="${logoUrl}" class="brand-logo-img" alt="${item.brand}" onerror="this.src='https://ui-avatars.com/api/?name=${item.brand}&background=7c6ef2&color=fff'">
        </div>
        <div class="history-info">
          <div class="history-brand">
            ${item.brand || 'Untitled'}
            <span class="issue-badge-count">${item.issues || 0} Issues</span>
          </div>
          <div class="history-meta">
            ${item.date || 'No Date'} • ${cleanUrl}
          </div>
        </div>
      </div>
      <div class="history-actions">
        <button class="history-btn-2d btn-delete" onclick="openModal('delete', '${item.id}')" title="Delete">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
        </button>
        <button class="history-btn-2d btn-share" onclick="openModal('share', '${item.id}')" title="Share">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
        </button>
        <button class="btn-view-report" onclick="window.location.href='/report/${item.id}'">
          View Report
        </button>
      </div>
    `;
    container.appendChild(el);
  });

  renderPagination();
}

function renderPagination() {
  const container = document.getElementById('paginationContainer');
  const totalPages = Math.ceil(mockHistory.length / itemsPerPage);
  
  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = `
    <button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="changePage(${currentPage - 1})">‹</button>
  `;

  for (let i = 1; i <= totalPages; i++) {
    html += `
      <button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="changePage(${i})">${i}</button>
    `;
  }

  html += `
    <button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="changePage(${currentPage + 1})">›</button>
  `;

  container.innerHTML = html;
}

function changePage(page) {
  currentPage = page;
  renderHistory();
}

function showError(msg) {
  console.error("Audit Error:", msg);
  document.getElementById('statusCard').style.display = 'none';
  document.getElementById('resultPanel').style.display = 'none';
  renderHistory(); 
  
  // Re-enable primary CTA
  const runBtn = document.getElementById('runBtn');
  runBtn.disabled = false;
  document.getElementById('btnText').textContent = 'Run Audit';
  document.getElementById('btnArrow').textContent = '→';

  const errCard = document.getElementById('errorCard');
  errCard.style.display = 'flex';
  errCard.style.flexDirection = 'column';
  document.getElementById('errorMsg').textContent = msg;
}

let activeShareId = null;

async function openModal(type, auditId, brandName = 'Latest Audit') {
  const overlay = document.getElementById('modalOverlay');
  overlay.style.display = 'flex';
  
  // Hide all modals first
  document.getElementById('shareModal').style.display = 'none';
  document.getElementById('deleteModal').style.display = 'none';
  document.getElementById('detailModal').style.display = 'none';
  
  if (type === 'share') {
    activeShareId = auditId;
    document.getElementById('shareModal').style.display = 'block';
  } else if (type === 'delete') {
    document.getElementById('deleteModal').style.display = 'block';
    document.getElementById('confirmDeleteBtn').onclick = () => deleteAudit(auditId);
  } else if (type === 'detail') {
    const detailModal = document.getElementById('detailModal');
    detailModal.style.display = 'flex';
    const header = document.getElementById('detailModalHeader');
    const content = document.getElementById('detailContent');
    
    const taskId = auditId; 
    console.log("Opening high-fidelity detail modal for Task:", taskId);

    try {
      const res  = await fetch(`/results/${taskId}`);
      const data = await res.json();

      if (!data.issues || data.issues.length === 0) {
        header.innerHTML = `<h3>${brandName} Audit</h3>`;
        content.innerHTML = '<div style="padding:4rem; text-align:center;">No data found for this audit.</div>';
        return;
      }

      // Render Premium Header
      header.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
          <div>
            <div style="color:var(--accent); font-weight:700; font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.4rem;">Audit Analysis Report</div>
            <h2 style="margin:0; font-family:'Outfit'; font-size:1.8rem;">${brandName}</h2>
          </div>
          <div style="display:flex; gap:1rem; align-items:center;">
             <span style="background:rgba(255,255,255,0.05); border:1px solid var(--border); padding:0.5rem 1rem; border-radius:8px; font-size:0.85rem; font-weight:600;">
               ${data.issues.length} Findings Detected
             </span>
             <button onclick="closeModal()" style="background:rgba(255,255,255,0.05); border:1px solid var(--border); color:#fff; padding:0.5rem 1rem; border-radius:8px; cursor:pointer; font-weight:600;">Close</button>
          </div>
        </div>
      `;

      // Render High-Fidelity Cards
      content.innerHTML = `
        <div class="report-grid" style="padding-top:1rem;">
          ${data.issues.map(issue => `
            <div class="report-card" style="background:rgba(255,255,255,0.02); border:1px solid var(--border); border-radius:24px; padding:2rem; margin-bottom:2.5rem; position:relative;">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1.5rem;">
                <div style="display:flex; gap:0.6rem;">
                  <div style="background:rgba(255,255,255,0.05); border:1px solid var(--border); padding:0.4rem 0.8rem; border-radius:6px; font-size:0.7rem; font-weight:700; color:var(--text-mid);">SEVERITY ${issue.Severity || '?'}</div>
                  <div style="background:rgba(255,255,255,0.05); border:1px solid var(--border); padding:0.4rem 0.8rem; border-radius:6px; font-size:0.7rem; font-weight:700; color:var(--text-mid);">${issue.Priority || 'P2'}</div>
                </div>
                <img src="${issue.Screenshot}" style="width:140px; height:80px; object-fit:cover; border-radius:8px; border:1px solid var(--border); cursor:pointer;" onclick="window.open('${issue.Screenshot}', '_blank')">
              </div>

              <div style="color:#ef4444; font-size:0.85rem; font-weight:700; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.8rem;">ISSUE - ${issue.Heuristic}</div>
              <h3 style="font-family:'Outfit'; font-size:1.7rem; margin:0 0 1.5rem 0; line-height:1.25; color:#fff; width:100%;">${issue['Issue Description']}</h3>

              <div style="background:rgba(124,110,242,0.08); border-left:4px solid var(--accent); padding:1.5rem; border-radius:4px 12px 12px 4px; margin:1.5rem 0;">
                <div style="color:var(--accent); font-size:0.65rem; font-weight:700; letter-spacing:0.1em; margin-bottom:0.6rem; display:flex; align-items:center; gap:0.4rem;">
                  <span>💡</span> STRATEGIC RECOMMENDATION
                </div>
                <div style="font-weight:600; font-size:1.1rem; line-height:1.5; color:#fff;">${issue.Recommendation}</div>
              </div>

              <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.2rem; margin-top:1.5rem;">
                <div style="background:rgba(255,255,255,0.03); padding:1.2rem; border-radius:12px; border:1px solid var(--border);">
                  <div style="color:var(--text-low); font-size:0.65rem; font-weight:700; letter-spacing:0.1em; margin-bottom:0.6rem; display:flex; align-items:center; gap:0.4rem;">
                    <span>🧠</span> BEHAVIORAL INSIGHT
                  </div>
                  <div style="font-size:0.85rem; color:var(--text-mid); line-height:1.5;">${issue['Behavioral Insight']}</div>
                </div>
                <div style="background:rgba(255,255,255,0.03); padding:1.2rem; border-radius:12px; border:1px solid var(--border);">
                  <div style="color:var(--text-low); font-size:0.65rem; font-weight:700; letter-spacing:0.1em; margin-bottom:0.6rem; display:flex; align-items:center; gap:0.4rem;">
                    <span>💬</span> ATTITUDINAL INSIGHT
                  </div>
                  <div style="font-size:0.85rem; color:var(--text-mid); line-height:1.5;">${issue['Attitudinal Insight']}</div>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    } catch (err) {
      console.error("Details Error:", err);
      content.innerHTML = `<div style="padding:4rem; text-align:center; color:#ef4444;">Error compiling report: ${err.message}</div>`;
    }
  }
}

function closeModal() {
  document.getElementById('modalOverlay').style.display = 'none';
  resetUI();
}

function showApiError(msg = "A valid Gemini API Key is required to power the heuristic engine.") {
  const modal = document.getElementById('apiErrorModal');
  const msgEl = document.getElementById('apiErrorMsg');
  if (modal && msgEl) {
    msgEl.textContent = msg;
    modal.style.display = 'flex';
  }
}

function closeApiError() {
  const modal = document.getElementById('apiErrorModal');
  if (modal) modal.style.display = 'none';
}

function showSuccessModal(title, msg) {
  document.getElementById('successTitle').textContent = title;
  document.getElementById('successMsg').textContent = msg;
  document.getElementById('modalOverlay').style.display = 'flex';
  document.getElementById('successModal').style.display = 'block';
  
  // Hide other modals
  document.getElementById('shareModal').style.display = 'none';
  document.getElementById('deleteModal').style.display = 'none';
}

function closeSuccessModal() {
  document.getElementById('modalOverlay').style.display = 'none';
  document.getElementById('successModal').style.display = 'none';
  resetUI();
}

async function sendInvite() {
  const email = document.getElementById('shareEmail').value;
  if (!email || !email.includes('@')) {
    showToast("Please enter a valid email address.");
    return;
  }

  const audit = mockHistory.find(m => m.id === activeShareId);
  if (!audit) {
    showToast("Error: Audit data not found.");
    return;
  }

  const btn = document.getElementById('inviteBtn');
  const originalText = btn.textContent;
  btn.textContent = "Sending...";
  btn.disabled = true;

  try {
    let issues = [];
    let payload = null;

    // Try LocalStorage first (bulletproof free-tier persistence fallback)
    const localDataStr = localStorage.getItem(`audit_report_${activeShareId}`);
    if (localDataStr) {
      try {
        const localData = JSON.parse(localDataStr);
        issues = localData.issues || [];
        payload = {
          brand: audit.brand,
          url: audit.url,
          issues: issues
        };
        console.log("[SHARE] Loaded audit report from LocalStorage for sharing.");
      } catch (e) {
        console.error("[SHARE] LocalStorage parse failed:", e);
      }
    }

    // Fallback: Fetch from the server if not present in LocalStorage
    if (!payload) {
      const res = await fetch(`/results/${activeShareId}`);
      if (!res.ok) throw new Error(`Report not found on server (${res.status})`);
      const data = await res.json();
      issues = data.issues || [];
      payload = {
        brand: audit.brand,
        url: audit.url,
        issues: issues
      };
      console.log("[SHARE] Loaded audit report from Server for sharing.");
    }

    const response = await fetch('/api/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: email,
        audit_data: payload 
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server Error (${response.status})`);
    }

    const result = await response.json();
    if (result.status === 'success') {
      showToast(`Invitation sent to ${email}!`);
      document.getElementById('shareEmail').value = '';
      showSuccessModal("Invitation Shared!", `Your UX Audit report for ${audit.brand} has been successfully dispatched to ${email}.`);
    } else {
      showToast("Sharing failed: " + result.message);
    }
  } catch (err) {
    console.error("Sharing Error Details:", err);
    showToast("Sharing failed: " + err.message);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

async function copyLink() {
  const shareLink = window.location.origin + '/report/' + activeShareId;
  try {
    await navigator.clipboard.writeText(shareLink);
    showToast("Report link copied to clipboard!");
  } catch (err) {
    // Fallback if clipboard API is blocked/unavailable
    const input = document.createElement('input');
    input.value = shareLink;
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    document.body.removeChild(input);
    showToast("Report link copied to clipboard!");
  }
  closeModal();
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.display = 'block';
  setTimeout(() => {
    toast.style.display = 'none';
  }, 3000);
}

function deleteAudit(id) {
  console.log("Attempting to delete audit:", id);
  const idx = mockHistory.findIndex(m => m.id === id);
  
  if (idx !== -1) {
    const brand = mockHistory[idx].brand || "Selected item";
    mockHistory.splice(idx, 1);
    saveHistory();
    
    // 1. Force Modal Close
    closeModal();
    
    // 2. Go to Home Screen
    resetUI();
    
    // 3. Visual Confirmation
    showToast(`Audit for "${brand}" has been successfully deleted.`);
    
    // Fallback if toast is somehow blocked/not visible
    console.log(`Deleted: ${brand}`);
  } else {
    console.error("Delete failed: ID not found in history.");
    closeModal();
    resetUI();
  }
}

function loadDetailContent(id) {
  const content = document.getElementById('detailContent');
  content.innerHTML = `
    <h2 style="margin-bottom:1rem;">Audit Details: ${id}</h2>
    <div style="background:var(--bg-sec); padding:2rem; border-radius:12px; border:1px dashed var(--border-hi); text-align:center; color:var(--text-dim);">
      [Mockup Detail View for ${id}]<br/>
      Heuristics and screenshots would be displayed here in full detail.
    </div>
  `;
}

// ── Theme Management ──
function initTheme() {
  const savedTheme = localStorage.getItem('ux-audit-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const target = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  localStorage.setItem('ux-audit-theme', target);
}

// Initialize theme as early as possible
initTheme();

// Allow Enter key to submit
document.addEventListener('DOMContentLoaded', () => {
  renderHistory(); // Initialize dashboard
  
  const handleEnter = (e) => {
    if (e.key === 'Enter') handleAction();
  };
  
  document.getElementById('urlInput').addEventListener('keydown', handleEnter);
  document.getElementById('apiKeyInput').addEventListener('keydown', handleEnter);
  
  // Initialize placeholder and saved keys
  updatePlaceholder();
  
  // Save API key on every keystroke for real-time persistence
  document.getElementById('apiKeyInput').addEventListener('input', (e) => {
    const provider = document.getElementById('providerSelect').value;
    const val = e.target.value.trim();
    if (val) {
      localStorage.setItem(`savedKey_${provider}`, val);
    }
  });

  // Ensure URL is always fresh on load as requested
  document.getElementById('urlInput').value = '';
});

// ── Bottom Sheet Logic ──

function openModelSheet() {
  if (window.innerWidth > 768) return; 
  const overlay = document.getElementById('modelBottomSheet');
  if (!overlay) return;
  overlay.style.display = 'flex';
  setTimeout(() => overlay.classList.add('active'), 10);
  
  const currentVal = document.getElementById('providerSelect').value;
  document.querySelectorAll('.sheet-option').forEach(opt => {
    const isSelected = opt.dataset.value === currentVal;
    opt.classList.toggle('active', isSelected);
    const check = opt.querySelector('.option-check');
    if (check) check.textContent = isSelected ? '✓' : '';
  });
}

function closeModelSheet() {
  const overlay = document.getElementById('modelBottomSheet');
  if (overlay) {
    overlay.classList.remove('active');
    setTimeout(() => overlay.style.display = 'none', 300);
  }
}

function selectModel(val) {
  const select = document.getElementById('providerSelect');
  if (select) {
    select.value = val;
    updatePlaceholder(); // Original logic to sync placeholder and keys
    
    // Update active state in UI immediately
    const label = val === 'openai' ? 'GPT-4o' : (val === 'anthropic' ? 'Claude' : 'Gemini');
    showToast(`Model switched to ${label}`);
  }
  closeModelSheet();
}
