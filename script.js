const thread = document.getElementById('thread');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const suggestions = document.getElementById('suggestions');
const newChatBtn = document.getElementById('newChatBtn');
const historyList = document.getElementById('historyList');
const historySearchInput = document.getElementById('historySearchInput');
const clearHistorySearchBtn = document.getElementById('clearHistorySearchBtn');
const historyCount = document.getElementById('historyCount');
const historyEmpty = document.getElementById('historyEmpty');
const sidebarName = document.getElementById('sidebarName');
const sidebarPrn = document.getElementById('sidebarPrn');

// Navigation elements
const chatSection = document.getElementById('chatSection');
const clubsSection = document.getElementById('clubsSection');
const tabChatBtn = document.getElementById('tabChatBtn');
const tabClubsBtn = document.getElementById('tabClubsBtn');
const headerSwitchClubsBtn = document.getElementById('headerSwitchClubsBtn');
const headerSwitchChatBtn = document.getElementById('headerSwitchChatBtn');

// Clubs directory elements
const clubsGrid = document.getElementById('clubsGrid');
const clubsEmpty = document.getElementById('clubsEmpty');
const categoryFilters = document.getElementById('categoryFilters');
const clubSearchInput = document.getElementById('clubSearchInput');
const clearSearchBtn = document.getElementById('clearSearchBtn');
const resetFilterBtn = document.getElementById('resetFilterBtn');
const totalClubsCount = document.getElementById('totalClubsCount');
const catCountAll = document.getElementById('catCountAll');

// Modal elements
const clubModal = document.getElementById('clubModal');
const mapModal = document.getElementById('mapModal');
const modalCloseBtn = document.getElementById('modalCloseBtn');
const modalCategory = document.getElementById('modalCategory');
const modalClubName = document.getElementById('modalClubName');
const modalAbbr = document.getElementById('modalAbbr');
const modalBody = document.getElementById('modalBody');
const modalPdfBtn = document.getElementById('modalPdfBtn');
const modalSourceBtn = document.getElementById('modalSourceBtn');
const modalAskAiBtn = document.getElementById('modalAskAiBtn');

let currentModalClub = null;
let allClubs = [];
let clubCategories = [];
let currentCategory = 'All';
let currentSearch = '';
let clubsLoaded = false;

// ---- API Base URL (auto-resolves for http, localhost, live-server and file://) ----
const API_BASE = (function() {
  if (window.location.protocol === 'file:' || (window.location.port && window.location.port !== '8000')) {
    return 'http://127.0.0.1:8000';
  }
  return '';
})();

// ---- Student session ----
let studentName = 'KITCOEK Student';
let studentPrn = 'Campus Assistant';

if (sidebarName) sidebarName.textContent = studentName;
if (sidebarPrn) sidebarPrn.textContent = studentPrn;

// Set greeting message
const greetingBubble = document.querySelector('.thread .row.bot .bubble p');
if (greetingBubble) {
  greetingBubble.innerHTML = `Hi! I'm the <strong class="bot-name-highlight">KITCOEK AI Assistant</strong>. Ask me about academic syllabus, timetables, examinations, campus navigation, or any of our <strong>18 Official Student Clubs</strong> (ISTE, E-Cell, SDC, Cultural, NSS, and more) — or pick a topic below to start.`;
}

// ---- Chat Appearance Theme Switcher ----
const themeWhiteBtn = document.getElementById('themeWhiteBtn');
const themeSpaceBtn = document.getElementById('themeSpaceBtn');

function setChatTheme(themeName) {
  const isWhite = (themeName === 'white');
  const activeTheme = isWhite ? 'white' : 'space';
  const currentInputValue = input ? input.value : '';

  // 1. Campus Chat Section
  if (chatSection) {
    chatSection.classList.toggle('chat-theme-white', isWhite);
    chatSection.classList.toggle('chat-theme-space', !isWhite);
  }

  // 2. Student Clubs Section
  if (clubsSection) {
    clubsSection.classList.toggle('theme-white', isWhite);
    clubsSection.classList.toggle('theme-space', !isWhite);
  }

  // 3. Club Details Modal
  if (clubModal) {
    clubModal.classList.toggle('theme-white', isWhite);
    clubModal.classList.toggle('theme-space', !isWhite);
  }

  // 4. Campus Map Lightbox Modal
  if (mapModal) {
    mapModal.classList.toggle('theme-white', isWhite);
    mapModal.classList.toggle('theme-space', !isWhite);
  }

  // 5. Update Switcher Buttons
  if (themeWhiteBtn) {
    themeWhiteBtn.classList.toggle('active', isWhite);
    themeWhiteBtn.setAttribute('aria-checked', isWhite ? 'true' : 'false');
  }
  if (themeSpaceBtn) {
    themeSpaceBtn.classList.toggle('active', !isWhite);
    themeSpaceBtn.setAttribute('aria-checked', !isWhite ? 'true' : 'false');
  }

  try {
    localStorage.setItem('kitcoek_chat_theme', activeTheme);
  } catch (e) {}

  // Ensure input content is preserved
  if (input && currentInputValue && input.value !== currentInputValue) {
    input.value = currentInputValue;
  }
}

if (themeWhiteBtn) {
  themeWhiteBtn.addEventListener('click', () => setChatTheme('white'));
  themeWhiteBtn.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setChatTheme('white');
    }
  });
}

if (themeSpaceBtn) {
  themeSpaceBtn.addEventListener('click', () => setChatTheme('space'));
  themeSpaceBtn.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setChatTheme('space');
    }
  });
}

// Initialize theme from localStorage or default to Space Blue Mode
const initialChatTheme = (function() {
  try {
    return localStorage.getItem('kitcoek_chat_theme');
  } catch(e) {
    return null;
  }
})() || 'space';

setChatTheme(initialChatTheme);

// ---- View Switching ----
function switchView(viewName) {
  if (viewName === 'clubs') {
    if (chatSection) chatSection.style.display = 'none';
    if (clubsSection) clubsSection.style.display = 'flex';
    if (tabChatBtn) tabChatBtn.classList.remove('active');
    if (tabClubsBtn) tabClubsBtn.classList.add('active');
    loadClubsDataIfNeeded();
  } else {
    if (clubsSection) clubsSection.style.display = 'none';
    if (chatSection) chatSection.style.display = 'flex';
    if (tabClubsBtn) tabClubsBtn.classList.remove('active');
    if (tabChatBtn) tabChatBtn.classList.add('active');
  }
}

if (tabChatBtn) tabChatBtn.addEventListener('click', () => switchView('chat'));
if (tabClubsBtn) tabClubsBtn.addEventListener('click', () => switchView('clubs'));
if (headerSwitchClubsBtn) headerSwitchClubsBtn.addEventListener('click', () => switchView('clubs'));
if (headerSwitchChatBtn) headerSwitchChatBtn.addEventListener('click', () => switchView('chat'));

// User avatar profile icon SVG
const userAvatarSvg = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" class="user-avatar-icon" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;

// Assistant avatar (official college logo with fallback K)
const botAvatarHtml = `<div class="avatar bot-avatar" aria-label="KITCOEK AI Assistant"><img src="kit-emblem.png?v=5.0" alt="KITCOEK" class="assistant-avatar-img" onerror="this.style.display='none'; this.parentNode.classList.add('avatar-fallback'); this.parentNode.innerText='K';"></div>`;

// ---- Chat Functions ----
function addRow(role, html){
  const row = document.createElement('div');
  row.className = 'row ' + role;
  const avatarHtml = role === 'bot'
    ? botAvatarHtml
    : `<div class="avatar user-avatar" aria-label="User">${userAvatarSvg}</div>`;
  row.innerHTML = `
    ${avatarHtml}
    <div class="bubble">${html}</div>
  `;
  thread.appendChild(row);
  thread.scrollTop = thread.scrollHeight;
  return row;
}

function showTyping(){
  const row = document.createElement('div');
  row.className = 'row bot';
  row.id = 'typingRow';
  row.innerHTML = `${botAvatarHtml}<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  thread.appendChild(row);
  thread.scrollTop = thread.scrollHeight;
}

function removeTyping(){
  const row = document.getElementById('typingRow');
  if (row) row.remove();
}

function renderSuggestions(list) {
  if (!suggestions) return;
  if (!list || list.length === 0) return;
  suggestions.innerHTML = '';
  list.forEach(q => {
    const btn = document.createElement('button');
    btn.className = 'chip';
    btn.dataset.q = q;
    btn.textContent = q;
    suggestions.appendChild(btn);
  });
}

function escapeHtml(str){
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function getCategoryClass(cat) {
  if (!cat) return '';
  const map = {
    'Technical': 'cat-technical',
    'Entrepreneurship': 'cat-entrepreneurship',
    'Cultural': 'cat-cultural',
    'Creative': 'cat-creative',
    'Social Service': 'cat-social-service',
    'Environment': 'cat-environment',
    'Leadership': 'cat-leadership',
    'Student Development': 'cat-student-development'
  };
  return map[cat] || '';
}

// ---- ChatGPT-Style Persistent Chat History ----
const STORAGE_KEY_CONVERSATIONS = 'kitcoek_chat_history_v1';
const STORAGE_KEY_ACTIVE_ID = 'kitcoek_active_conv_id';

let conversations = [];
let activeConvId = null;
let historySearchQuery = '';

function getWelcomeMessageHtml() {
  return `<p>Hi! I'm the <strong class="bot-name-highlight">KITCOEK AI Assistant</strong>. Ask me about academic syllabus, timetables, examinations, campus navigation, or any of our <strong>18 Official Student Clubs</strong> (ISTE, E-Cell, SDC, Cultural, NSS, and more) — or pick a topic below to start.</p>`;
}

function loadStoredConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_CONVERSATIONS);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    return null;
  } catch (err) {
    console.warn('Storage read warning:', err);
    return null;
  }
}

function saveStoredConversations() {
  try {
    localStorage.setItem(STORAGE_KEY_CONVERSATIONS, JSON.stringify(conversations));
    if (activeConvId) {
      localStorage.setItem(STORAGE_KEY_ACTIVE_ID, activeConvId);
    }
  } catch (err) {
    console.warn('Storage write warning:', err);
  }
}

function generateConvId() {
  return 'conv_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
}

function generateConversationTitle(text) {
  if (!text) return 'New Conversation';
  let clean = text.trim()
    .replace(/[\r\n]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^[\s\W]+/, '');

  clean = clean.replace(/^(can you please tell me about|please tell me about|tell me about|what is the purpose of|what is the|where can i find|where can i get|how do i|how can i|what are the)\s+/i, '');

  if (clean.length > 32) {
    const cut = clean.slice(0, 32);
    const lastSpace = cut.lastIndexOf(' ');
    clean = (lastSpace > 18 ? cut.slice(0, lastSpace) : cut) + '…';
  }

  if (clean.length > 0) {
    clean = clean.charAt(0).toUpperCase() + clean.slice(1);
  }
  return clean || 'New Conversation';
}

function createNewConversation(title = 'New Conversation') {
  const now = Date.now();
  return {
    id: generateConvId(),
    title: title,
    createdAt: now,
    updatedAt: now,
    messages: [
      {
        role: 'bot',
        html: getWelcomeMessageHtml(),
        timestamp: now
      }
    ]
  };
}

function getActiveConversation() {
  if (!activeConvId) return null;
  return conversations.find(c => c.id === activeConvId) || null;
}

function renderActiveThread() {
  if (!thread) return;
  thread.innerHTML = '';
  const current = getActiveConversation();
  if (!current || !current.messages || current.messages.length === 0) {
    addRow('bot', getWelcomeMessageHtml());
    return;
  }
  current.messages.forEach(msg => {
    addRow(msg.role, msg.html);
  });
  setTimeout(() => {
    thread.scrollTop = thread.scrollHeight;
  }, 40);
}

function renderHistoryList() {
  if (!historyList) return;
  historyList.innerHTML = '';

  const sorted = [...conversations].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));

  if (historyCount) {
    historyCount.textContent = conversations.length;
  }

  const q = (historySearchQuery || '').trim().toLowerCase();
  const filtered = q
    ? sorted.filter(c => (c.title || '').toLowerCase().includes(q))
    : sorted;

  if (historyEmpty) {
    historyEmpty.style.display = filtered.length === 0 ? 'flex' : 'none';
  }

  filtered.forEach(conv => {
    const li = document.createElement('li');
    li.className = 'history-item' + (conv.id === activeConvId ? ' active' : '');
    li.dataset.id = conv.id;

    const iconSvg = `<svg class="history-item-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
    const renameSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>`;
    const deleteSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;

    li.innerHTML = `
      <div class="history-item-content">
        ${iconSvg}
        <span class="history-title" title="${escapeHtml(conv.title)}">${escapeHtml(conv.title)}</span>
      </div>
      <div class="history-item-actions">
        <button type="button" class="history-action-btn rename-btn" title="Rename conversation" aria-label="Rename conversation">
          ${renameSvg}
        </button>
        <button type="button" class="history-action-btn delete-btn" title="Delete conversation" aria-label="Delete conversation">
          ${deleteSvg}
        </button>
      </div>
    `;

    li.addEventListener('click', (e) => {
      if (e.target.closest('.history-item-actions') || li.classList.contains('editing')) return;
      selectConversation(conv.id);
    });

    const renameBtn = li.querySelector('.rename-btn');
    if (renameBtn) {
      renameBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        startRenaming(conv.id, li);
      });
    }

    const deleteBtn = li.querySelector('.delete-btn');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        confirmDeleteConversation(conv.id);
      });
    }

    historyList.appendChild(li);
  });
}

function startRenaming(convId, liElement) {
  const conv = conversations.find(c => c.id === convId);
  if (!conv || !liElement) return;

  liElement.classList.add('editing');
  liElement.innerHTML = `
    <input type="text" class="history-rename-input" value="${escapeHtml(conv.title)}" maxlength="45" aria-label="Rename conversation">
    <div class="history-rename-actions">
      <button type="button" class="rename-confirm-btn" title="Save">✓</button>
      <button type="button" class="rename-cancel-btn" title="Cancel">✕</button>
    </div>
  `;

  const inputEl = liElement.querySelector('.history-rename-input');
  const confirmBtn = liElement.querySelector('.rename-confirm-btn');
  const cancelBtn = liElement.querySelector('.rename-cancel-btn');

  if (inputEl) {
    inputEl.focus();
    inputEl.select();

    const doSave = () => {
      const val = inputEl.value.trim();
      if (val && val !== conv.title) {
        conv.title = val;
        conv.updatedAt = Date.now();
        saveStoredConversations();
        broadcastHistoryChange();
      }
      renderHistoryList();
    };

    const doCancel = () => {
      renderHistoryList();
    };

    confirmBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      doSave();
    });

    cancelBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      doCancel();
    });

    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        doSave();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        doCancel();
      }
    });

    inputEl.addEventListener('click', (e) => e.stopPropagation());
  }
}

function confirmDeleteConversation(convId) {
  const conv = conversations.find(c => c.id === convId);
  if (!conv) return;

  const confirmed = window.confirm(`Are you sure you want to delete the conversation "${conv.title}"?`);
  if (!confirmed) return;

  conversations = conversations.filter(c => c.id !== convId);

  if (activeConvId === convId) {
    if (conversations.length > 0) {
      activeConvId = conversations[0].id;
    } else {
      const fresh = createNewConversation();
      conversations = [fresh];
      activeConvId = fresh.id;
    }
    renderActiveThread();
  }

  saveStoredConversations();
  renderHistoryList();
  broadcastHistoryChange();
}

function selectConversation(convId) {
  if (activeConvId === convId) {
    switchView('chat');
    return;
  }
  const conv = conversations.find(c => c.id === convId);
  if (!conv) return;

  activeConvId = convId;
  saveStoredConversations();
  renderActiveThread();
  renderHistoryList();
  switchView('chat');
  if (input) input.focus();
}

function handleNewConversationClick() {
  switchView('chat');
  const current = getActiveConversation();
  const hasUserMessages = current && current.messages && current.messages.some(m => m.role === 'user');
  if (current && !hasUserMessages) {
    if (input) input.focus();
    return;
  }

  const newConv = createNewConversation();
  conversations.unshift(newConv);
  activeConvId = newConv.id;
  saveStoredConversations();
  renderActiveThread();
  renderHistoryList();
  broadcastHistoryChange();
  if (input) input.focus();
}

let syncChannel = null;
try {
  if (typeof BroadcastChannel !== 'undefined') {
    syncChannel = new BroadcastChannel('kitcoek_chat_sync_v1');
    syncChannel.onmessage = (event) => {
      if (event.data && event.data.type === 'SYNC') {
        syncFromStorage();
      }
    };
  }
} catch (e) {
  console.warn('BroadcastChannel error:', e);
}

function broadcastHistoryChange() {
  if (syncChannel) {
    try {
      syncChannel.postMessage({ type: 'SYNC', timestamp: Date.now() });
    } catch (e) {}
  }
}

window.addEventListener('storage', (e) => {
  if (e.key === STORAGE_KEY_CONVERSATIONS || e.key === STORAGE_KEY_ACTIVE_ID) {
    syncFromStorage();
  }
});

function syncFromStorage() {
  const stored = loadStoredConversations();
  if (!stored) return;

  conversations = stored;
  const storedActiveId = localStorage.getItem(STORAGE_KEY_ACTIVE_ID);

  if (storedActiveId && conversations.some(c => c.id === storedActiveId)) {
    activeConvId = storedActiveId;
  } else if (!conversations.some(c => c.id === activeConvId)) {
    activeConvId = conversations.length > 0 ? conversations[0].id : null;
  }

  renderHistoryList();

  const current = getActiveConversation();
  if (current) {
    const threadRowCount = thread ? thread.querySelectorAll('.row:not(#typingRow)').length : 0;
    if (threadRowCount !== current.messages.length) {
      renderActiveThread();
    }
  }
}

if (historySearchInput) {
  historySearchInput.addEventListener('input', () => {
    historySearchQuery = historySearchInput.value;
    if (clearHistorySearchBtn) {
      clearHistorySearchBtn.style.display = historySearchQuery ? 'block' : 'none';
    }
    renderHistoryList();
  });
}

if (clearHistorySearchBtn) {
  clearHistorySearchBtn.addEventListener('click', () => {
    if (historySearchInput) {
      historySearchInput.value = '';
      historySearchQuery = '';
      clearHistorySearchBtn.style.display = 'none';
      historySearchInput.focus();
    }
    renderHistoryList();
  });
}

function initConversationHistory() {
  const stored = loadStoredConversations();
  if (stored && stored.length > 0) {
    conversations = stored;
    const storedActiveId = localStorage.getItem(STORAGE_KEY_ACTIVE_ID);
    if (storedActiveId && conversations.some(c => c.id === storedActiveId)) {
      activeConvId = storedActiveId;
    } else {
      activeConvId = conversations[0].id;
    }
  } else {
    const initial = createNewConversation();
    conversations = [initial];
    activeConvId = initial.id;
    saveStoredConversations();
  }

  renderHistoryList();
  renderActiveThread();
}

async function sendMessage(text){
  const trimmed = text.trim();
  if (!trimmed) return;

  let currentConv = getActiveConversation();
  if (!currentConv) {
    currentConv = createNewConversation();
    conversations.unshift(currentConv);
    activeConvId = currentConv.id;
  }

  const userMsgCount = currentConv.messages.filter(m => m.role === 'user').length;
  if (userMsgCount === 0 || currentConv.title === 'New Conversation') {
    currentConv.title = generateConversationTitle(trimmed);
  }

  const userHtml = `<p>${escapeHtml(trimmed)}</p>`;
  currentConv.messages.push({
    role: 'user',
    html: userHtml,
    timestamp: Date.now()
  });
  currentConv.updatedAt = Date.now();
  saveStoredConversations();
  renderHistoryList();
  broadcastHistoryChange();

  addRow('user', userHtml);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  showTyping();

  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: trimmed,
        session_id: currentConv.id,
        student_prn: studentPrn,
        student_name: studentName
      })
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const data = await response.json();
    removeTyping();

    let botHtml = data.reply;

    if (data.club_details) {
      const c = data.club_details;
      const catClass = getCategoryClass(c.category);
      botHtml += `
        <div class="chat-club-card">
          <div class="chat-club-header">
            <span class="chat-club-category ${catClass}">${escapeHtml(c.category || 'Official Club')}</span>
            <span class="chat-club-year">${escapeHtml(c.academic_year || 'A.Y. 2025–26')}</span>
          </div>
          <h4>${escapeHtml(c.name)} ${c.abbr ? `(${escapeHtml(c.abbr)})` : ''}</h4>
          <p>${escapeHtml(c.tagline || (c.description ? c.description.slice(0, 150) + '…' : ''))}</p>
          <div class="chat-club-actions">
            <button class="chat-club-btn chat-club-btn-secondary view-club-btn" data-club-id="${escapeHtml(c.id)}">
              🔍 View Full Profile
            </button>
            ${c.pdf_url ? `<a href="${c.pdf_url}" target="_blank" class="chat-club-btn chat-club-btn-primary">
              📄 Official PDF Report
            </a>` : ''}
          </div>
        </div>
      `;
    }

    if (data.location_details) {
      const loc = data.location_details;
      botHtml += `
        <div class="nav-box nav-box-location">
          <p class="nav-box-title"><strong>Campus Location:</strong> ${escapeHtml(loc.building)} — ${escapeHtml(loc.floor)}</p>
          ${loc.landmark ? `<p class="nav-box-landmark"><em>Landmark: ${escapeHtml(loc.landmark)}</em></p>` : ''}
          ${loc.room_number ? `<p class="nav-box-rooms"><strong>Block / Rooms:</strong> ${escapeHtml(loc.room_number)}</p>` : ''}
          <div class="map-thumbnail-container open-map-modal-btn" title="Click to open Aerial Campus Map">
            <img src="campus_map.jpg" alt="Aerial Campus Map Preview">
            <div class="map-thumbnail-overlay">
              <span>🗺️ Official Aerial Campus Map (Tap to view)</span>
              <span>🔍 Zoom</span>
            </div>
          </div>
          <div class="nav-box-actions">
            <button class="map-link-btn map-link-btn-primary open-map-modal-btn" type="button">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
              View Aerial Map
            </button>
            <a href="campus_map.jpg" target="_blank" class="map-link-btn map-link-btn-secondary">
              ↗ Open in Tab
            </a>
          </div>
        </div>
      `;
    }

    if (data.vmedulife_guide) {
      const g = data.vmedulife_guide;
      const icon = g.type === 'result' ? '📊' : (g.type === 'attendance' ? '📅' : '📚');
      const badgeText = g.type === 'result' ? 'RESULTS & REVIEWS' : (g.type === 'attendance' ? 'ATTENDANCE TRACKER' : 'MY LEARNINGS & NOTES');
      const descText = g.type === 'result'
        ? 'Log in to open Assessment / Exam Forms, view your semester grade cards, and submit Answer Sheet Review appeals.'
        : (g.type === 'attendance'
          ? 'Log in to Academic Planning → Attendance to track your Daily, Weekly, and Monthly attendance records.'
          : 'Log in to Academic Planning → Start Learning → My Learnings to access teacher-uploaded study notes and courses.');
      botHtml += `
        <div class="nav-box nav-box-portal">
          <div class="vmedulife-header">
            <span class="vmedulife-badge">${icon} ${badgeText}</span>
            <p class="nav-box-title"><strong>KITCOEK Student Portal (vMedulife):</strong></p>
          </div>
          <p class="nav-box-desc">${descText}</p>
          <div class="nav-box-actions">
            <a href="${g.portal_url}" target="_blank" class="map-link-btn map-link-btn-portal">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Open vMedulife Student Portal ↗
            </a>
          </div>
        </div>
      `;
    } else if (data.portal_url) {
      botHtml += `
        <div class="nav-box nav-box-portal">
          <p class="nav-box-title"><strong>KITCOEK Student Portal (vMedulife) &amp; LMS:</strong></p>
          <p class="nav-box-desc">
            Access semester examination results, SGPA/CGPA grade cards, LMS course notes, and attendance tracking.
          </p>
          <div class="nav-box-actions">
            <a href="${data.portal_url}" target="_blank" class="map-link-btn map-link-btn-portal">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Open vMedulife Student Portal ↗
            </a>
          </div>
        </div>
      `;
    }

    if (data.notes_url) {
      botHtml += `
        <div class="nav-box nav-box-notes">
          <p class="nav-box-title"><strong>KITCOEK Subject &amp; Handwritten Notes:</strong></p>
          <p class="nav-box-desc">
            Access verified PDF notes for Statistical Methods (Unit 4: Analysis of Variance), SPS (Unit 3), and department study materials.
          </p>
          <div class="nav-box-actions">
            <a href="${data.notes_url}" target="_blank" class="map-link-btn map-link-btn-primary">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              📄 Open Notes PDF / Folder ↗
            </a>
            <a href="https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy" target="_blank" class="map-link-btn map-link-btn-secondary">
              📁 View All Notes in Drive
            </a>
          </div>
        </div>
      `;
    }

    if (data.timetable_url) {
      botHtml += `
        <div class="nav-box nav-box-timetable">
          <p class="nav-box-title"><strong>KITCOEK Class &amp; Department Timetables:</strong></p>
          <p class="nav-box-desc">
            Access class schedules for CSBS (SY, TY, Final Year) and other institute department timetables.
          </p>
          <div class="nav-box-actions">
            <a href="${data.timetable_url}" target="_blank" class="map-link-btn map-link-btn-primary">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              📅 Open Timetable File ↗
            </a>
            <a href="https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT" target="_blank" class="map-link-btn map-link-btn-secondary">
              📁 View Timetables Drive Folder
            </a>
          </div>
        </div>
      `;
    }

    if (Array.isArray(data.notices_details) && data.notices_details.length > 0) {
      const noticeItemsHtml = data.notices_details.map(n => `
        <div class="notice-item">
          <div class="notice-item-main">
            <span class="notice-item-date">📅 ${escapeHtml(n.date || 'Recent Notice')}</span>
            <div class="notice-item-title">${escapeHtml(n.title)}</div>
          </div>
          ${n.file_url ? `
            <a href="${n.file_url}" target="_blank" class="notice-download-btn" title="Download Official Circular (PDF)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              PDF ↗
            </a>
          ` : ''}
        </div>
      `).join('');

      botHtml += `
        <div class="nav-box nav-box-notices">
          <div class="notice-card-header">
            <div class="notice-badge">📌 Official KITCOEK Notice Board &amp; Timetables</div>
            <span class="notice-live-dot">● Live from kitcoek.in/notice</span>
          </div>
          <div class="notice-items-container">
            ${noticeItemsHtml}
          </div>
          <div class="nav-box-actions" style="margin-top:8px;">
            <a href="${data.notice_board_url || 'https://www.kitcoek.in/notice'}" target="_blank" class="map-link-btn map-link-btn-notice">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              View Official Notice Board (kitcoek.in/notice) ↗
            </a>
          </div>
        </div>
      `;
    }

    if (Array.isArray(data.academic_calendars) && data.academic_calendars.length > 0) {
      const calItemsHtml = data.academic_calendars.map(cal => `
        <div class="notice-item">
          <div class="notice-item-main">
            <span class="notice-item-date">📅 Academic Year ${escapeHtml(cal.academic_year)} (${escapeHtml(cal.term)})</span>
            <div class="notice-item-title">${escapeHtml(cal.title)}</div>
          </div>
          <a href="${cal.pdf_url}" target="_blank" class="notice-download-btn" title="Open Academic Calendar PDF">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            Calendar PDF ↗
          </a>
        </div>
      `).join('');

      botHtml += `
        <div class="nav-box nav-box-calendar">
          <div class="notice-card-header">
            <div class="notice-badge">🗓️ Official KITCOEK Academic Calendars</div>
          </div>
          <div class="notice-items-container">
            ${calItemsHtml}
          </div>
          <div class="nav-box-actions" style="margin-top:8px;">
            <a href="${data.notice_board_url || 'https://www.kitcoek.in/notice'}" target="_blank" class="map-link-btn map-link-btn-notice">
              📌 Official Campus Notices &amp; Schedules ↗
            </a>
          </div>
        </div>
      `;
    }

    if (data.meraki_reels && data.meraki_reels.length > 0) {
      const reelsHtml = data.meraki_reels.map((r, i) => `
        <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer" class="reel-link-btn">
          <div class="reel-btn-left">
            <span class="reel-tag-badge">${escapeHtml(r.tag || `Reel ${i + 1}`)}</span>
            <span class="reel-btn-title">${escapeHtml(r.title)}</span>
          </div>
          <span class="reel-btn-arrow">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            Watch
          </span>
        </a>
      `).join('');

      botHtml += `
        <div class="nav-box nav-box-reels">
          <div class="reels-card-header">
            <div class="reels-badge">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>
              MERAKI Official Instagram Reels &amp; Gathering
            </div>
            <span class="reels-live-tag">🎉 Flagship Cultural Fest</span>
          </div>
          <p class="nav-box-desc" style="margin-bottom:8px;">
            Watch official Instagram Reels from KITCOEK's annual cultural gathering — featuring dance competitions, stage performances, concerts, and aftermovies!
          </p>
          <div class="reels-links-container">
            ${reelsHtml}
          </div>
        </div>
      `;
    }

    currentConv.messages.push({
      role: 'bot',
      html: botHtml,
      timestamp: Date.now()
    });
    currentConv.updatedAt = Date.now();
    saveStoredConversations();
    renderHistoryList();
    broadcastHistoryChange();

    addRow('bot', botHtml);

    if (data.follow_up_questions && data.follow_up_questions.length > 0) {
      renderSuggestions(data.follow_up_questions);
    }
  } catch (err) {
    console.error('API Error:', err);
    removeTyping();
    const errorHtml = `<p class="chat-error-msg">⚠️ Unable to reach KITCOEK backend server. Please verify backend is running on port 8000.</p>`;
    currentConv.messages.push({
      role: 'bot',
      html: errorHtml,
      timestamp: Date.now()
    });
    currentConv.updatedAt = Date.now();
    saveStoredConversations();
    renderHistoryList();
    broadcastHistoryChange();
    addRow('bot', errorHtml);
  } finally {
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
    setTimeout(() => {
      thread.scrollTop = thread.scrollHeight;
    }, 100);
  }
}

sendBtn.addEventListener('click', () => sendMessage(input.value));
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    sendMessage(input.value);
  }
});
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});

// Speech-to-Text Voice Dictation
let recognition = null;
let isRecording = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-IN';

  recognition.onstart = () => {
    isRecording = true;
    if (micBtn) {
      micBtn.classList.add('listening');
      micBtn.setAttribute('title', 'Listening... Speak now');
    }
  };

  recognition.onresult = (event) => {
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      transcript += event.results[i][0].transcript;
    }
    if (input) {
      input.value = transcript;
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    }
  };

  recognition.onerror = (event) => {
    console.warn('Speech recognition error:', event.error);
    stopRecording();
  };

  recognition.onend = () => {
    stopRecording();
  };
}

function stopRecording() {
  isRecording = false;
  if (micBtn) {
    micBtn.classList.remove('listening');
    micBtn.setAttribute('title', 'Voice Input (Speech-to-Text)');
  }
}

if (micBtn) {
  micBtn.addEventListener('click', () => {
    if (!recognition) {
      alert('Speech Recognition is not supported by your current browser. Please try Google Chrome or Microsoft Edge.');
      return;
    }
    if (isRecording) {
      recognition.stop();
    } else {
      try {
        recognition.start();
      } catch (err) {
        console.warn('Recognition start error:', err);
      }
    }
  });
}

suggestions.addEventListener('click', (e) => {
  const btn = e.target.closest('.chip');
  if (btn && btn.dataset.q) {
    sendMessage(btn.dataset.q);
  }
});

if (newChatBtn) {
  newChatBtn.addEventListener('click', handleNewConversationClick);
}

// Initialize history on load
initConversationHistory();

// ---- Clubs Directory Functions ----
async function loadClubsDataIfNeeded() {
  if (clubsLoaded) return;
  try {
    const [clubsRes, catsRes] = await Promise.all([
      fetch(`${API_BASE}/api/clubs`),
      fetch(`${API_BASE}/api/clubs/categories`)
    ]);
    if (!clubsRes.ok) throw new Error('Failed to load clubs');
    allClubs = await clubsRes.json();
    if (catsRes.ok) {
      clubCategories = await catsRes.json();
    }
    clubsLoaded = true;
    renderCategories();
    renderClubs();
  } catch (e) {
    console.error('Clubs fetch error:', e);
    if (clubsGrid) {
      clubsGrid.innerHTML = `
        <div class="clubs-loading">
          <p class="clubs-error-msg">⚠️ Unable to load clubs directory from backend. Please ensure the backend server is running.</p>
        </div>
      `;
    }
  }
}

function renderCategories() {
  if (!categoryFilters) return;
  if (catCountAll) catCountAll.textContent = allClubs.length;
  if (totalClubsCount) totalClubsCount.textContent = `${allClubs.length} Official Clubs`;

  categoryFilters.innerHTML = `
    <button class="cat-pill ${currentCategory === 'All' ? 'active' : ''}" data-category="All">
      All (${allClubs.length})
    </button>
  `;

  clubCategories.forEach(c => {
    const btn = document.createElement('button');
    btn.className = `cat-pill ${currentCategory === c.category ? 'active' : ''}`;
    btn.dataset.category = c.category;
    btn.textContent = `${c.category} (${c.count})`;
    categoryFilters.appendChild(btn);
  });
}

function renderClubs() {
  if (!clubsGrid) return;
  const filtered = allClubs.filter(club => {
    const matchCat = (currentCategory === 'All' || club.category === currentCategory);
    if (!matchCat) return false;
    if (!currentSearch) return true;
    const s = currentSearch.toLowerCase();
    const nameMatch = club.name.toLowerCase().includes(s);
    const abbrMatch = club.abbr && club.abbr.toLowerCase().includes(s);
    const descMatch = club.description && club.description.toLowerCase().includes(s);
    const skillsMatch = Array.isArray(club.skills_developed) 
      ? club.skills_developed.some(sk => sk.toLowerCase().includes(s))
      : (club.skills_developed && club.skills_developed.toLowerCase().includes(s));
    const actMatch = Array.isArray(club.major_activities)
      ? club.major_activities.some(a => (typeof a === 'string' ? a : a.event || a.name || '').toLowerCase().includes(s))
      : (club.major_activities && club.major_activities.toLowerCase().includes(s));
    const coordMatch = club.faculty_coordinator && club.faculty_coordinator.toLowerCase().includes(s);
    return nameMatch || abbrMatch || descMatch || skillsMatch || actMatch || coordMatch;
  });

  if (filtered.length === 0) {
    clubsGrid.innerHTML = '';
    if (clubsEmpty) clubsEmpty.style.display = 'block';
    return;
  }

  if (clubsEmpty) clubsEmpty.style.display = 'none';

  clubsGrid.innerHTML = filtered.map(c => {
    const catClass = getCategoryClass(c.category);
    const skills = Array.isArray(c.skills_developed) ? c.skills_developed.slice(0, 3) : [];
    const skillsHtml = skills.map(sk => `<span class="skill-pill">${escapeHtml(sk)}</span>`).join('');
    
    return `
      <div class="club-card" data-club-id="${escapeHtml(c.id)}">
        <div class="club-card-top">
          <span class="club-category-badge ${catClass}">${escapeHtml(c.category)}</span>
          <span class="club-year-tag">${escapeHtml(c.academic_year || '2025–26')}</span>
        </div>
        <h3 class="club-card-title">
          ${escapeHtml(c.name)}
          ${c.abbr ? `<span class="club-card-abbr">${escapeHtml(c.abbr)}</span>` : ''}
        </h3>
        <p class="club-card-desc">${escapeHtml(c.tagline || c.description || '')}</p>
        
        ${skillsHtml ? `<div class="club-card-skills">${skillsHtml}</div>` : ''}

        ${c.faculty_coordinator ? `
          <div class="club-card-coordinator">
            <strong>Coordinator:</strong> ${escapeHtml(c.faculty_coordinator)}
          </div>
        ` : ''}

        <div class="club-card-actions">
          <button class="btn-card btn-card-primary view-club-btn" data-club-id="${escapeHtml(c.id)}">
            View Details
          </button>
          ${c.pdf_url ? `
            <a href="${c.pdf_url}" target="_blank" class="btn-card btn-card-secondary" title="Official PDF Report">
              📄 Report
            </a>
          ` : ''}
          <button class="btn-card btn-card-secondary ask-club-btn" data-club-name="${escapeHtml(c.name)}" title="Ask AI">
            💬 Ask AI
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// ---- Club Details Modal ----
function openClubModal(clubId) {
  const club = allClubs.find(c => c.id === clubId);
  if (!club) return;
  currentModalClub = club;

  modalCategory.textContent = club.category;
  modalCategory.className = `modal-category-badge ${getCategoryClass(club.category)}`;
  modalClubName.textContent = club.name;
  modalAbbr.textContent = club.abbr ? `Abbreviation: ${club.abbr}` : '';

  // Objectives
  let objList = '';
  if (Array.isArray(club.objectives) && club.objectives.length > 0) {
    objList = `<ul>${club.objectives.map(o => `<li>${escapeHtml(o)}</li>`).join('')}</ul>`;
  } else if (club.objectives) {
    objList = `<p>${escapeHtml(club.objectives)}</p>`;
  }

  // Major Activities
  let actList = '';
  if (Array.isArray(club.major_activities) && club.major_activities.length > 0) {
    actList = `<ul>${club.major_activities.map(a => {
      if (typeof a === 'object' && a !== null) {
        const title = a.name || a.event || a.title || JSON.stringify(a);
        const desc = a.description || a.details ? ` — <em>${escapeHtml(a.description || a.details)}</em>` : '';
        return `<li><strong>${escapeHtml(title)}</strong>${desc}</li>`;
      }
      return `<li>${escapeHtml(String(a))}</li>`;
    }).join('')}</ul>`;
  } else if (club.major_activities) {
    actList = `<p>${escapeHtml(club.major_activities)}</p>`;
  }

  // Skills Developed
  let skillsPills = '';
  if (Array.isArray(club.skills_developed) && club.skills_developed.length > 0) {
    skillsPills = `<div class="club-card-skills" style="margin-top:6px;">${
      club.skills_developed.map(s => `<span class="skill-pill" style="font-size:12px; padding:3px 9px;">${escapeHtml(s)}</span>`).join('')
    }</div>`;
  } else if (club.skills_developed) {
    skillsPills = `<p>${escapeHtml(club.skills_developed)}</p>`;
  }

  modalBody.innerHTML = `
    <div class="modal-meta-grid">
      <div class="modal-meta-item">
        <strong>Academic Year</strong>
        <span>${escapeHtml(club.academic_year || '2025–26')}</span>
      </div>
      <div class="modal-meta-item">
        <strong>Established</strong>
        <span>${escapeHtml(club.establishment_year || 'Officially Registered')}</span>
      </div>
      <div class="modal-meta-item">
        <strong>Faculty Coordinator</strong>
        <span>${escapeHtml(club.faculty_coordinator || 'Refer to Department / Report')}</span>
      </div>
      <div class="modal-meta-item">
        <strong>Student Coordinators</strong>
        <span>${escapeHtml(club.student_coordinators || 'Published in Annual Report')}</span>
      </div>
    </div>

    ${club.description ? `
      <div class="modal-section">
        <span class="modal-section-title">About the Club</span>
        <p>${escapeHtml(club.description)}</p>
      </div>
    ` : ''}

    ${objList ? `
      <div class="modal-section">
        <span class="modal-section-title">Main Objectives</span>
        ${objList}
      </div>
    ` : ''}

    ${actList ? `
      <div class="modal-section">
        <span class="modal-section-title">Major Activities &amp; Events (2025–26)</span>
        ${actList}
      </div>
    ` : ''}

    ${(club.meraki_reels && Array.isArray(club.meraki_reels) && club.meraki_reels.length > 0) ? `
      <div class="modal-section modal-section-reels">
        <span class="modal-section-title">🎬 MERAKI Official Instagram Reels</span>
        <p style="font-size:13px; color:var(--text-muted); margin-bottom:10px;">
          Watch official highlights, dance performances, stage acts, and campus celebrations:
        </p>
        <div class="meraki-reels-grid">
          ${club.meraki_reels.map((r, i) => `
            <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer" class="meraki-reel-card">
              <div class="reel-card-top">
                <span class="reel-pill">${escapeHtml(r.tag || `Reel ${i + 1}`)}</span>
                <span class="reel-insta-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>
                </span>
              </div>
              <div class="reel-card-title">${escapeHtml(r.title)}</div>
              <div class="reel-card-action">
                <span>Watch Reel</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    ` : ''}

    ${skillsPills ? `
      <div class="modal-section">
        <span class="modal-section-title">Skills Students Can Develop</span>
        ${skillsPills}
      </div>
    ` : ''}

    ${club.achievements ? `
      <div class="modal-section">
        <span class="modal-section-title">Achievements &amp; Annual Highlights</span>
        <p>${escapeHtml(club.achievements)}</p>
      </div>
    ` : ''}

    ${club.eligibility ? `
      <div class="modal-section">
        <span class="modal-section-title">Membership &amp; Eligibility</span>
        <p>${escapeHtml(club.eligibility)}</p>
      </div>
    ` : ''}
  `;

  // Links
  if (club.pdf_url) {
    modalPdfBtn.href = club.pdf_url;
    modalPdfBtn.style.display = 'inline-flex';
  } else {
    modalPdfBtn.style.display = 'none';
  }

  modalSourceBtn.href = club.source_url || 'https://www.kitcoek.in/studentClubs';

  clubModal.style.display = 'flex';
}

function closeClubModal() {
  if (clubModal) clubModal.style.display = 'none';
  currentModalClub = null;
}

if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeClubModal);
if (clubModal) {
  clubModal.addEventListener('click', (e) => {
    if (e.target === clubModal) closeClubModal();
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && clubModal && clubModal.style.display === 'flex') {
    closeClubModal();
  }
});

if (modalAskAiBtn) {
  modalAskAiBtn.addEventListener('click', () => {
    if (currentModalClub) {
      const q = `Tell me about ${currentModalClub.name}`;
      closeClubModal();
      switchView('chat');
      sendMessage(q);
    }
  });
}

// Category filter click
if (categoryFilters) {
  categoryFilters.addEventListener('click', (e) => {
    const pill = e.target.closest('.cat-pill');
    if (pill && pill.dataset.category) {
      currentCategory = pill.dataset.category;
      document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      renderClubs();
    }
  });
}

// Search input
if (clubSearchInput) {
  clubSearchInput.addEventListener('input', (e) => {
    currentSearch = e.target.value.trim();
    if (clearSearchBtn) {
      clearSearchBtn.style.display = currentSearch ? 'block' : 'none';
    }
    renderClubs();
  });
}

if (clearSearchBtn) {
  clearSearchBtn.addEventListener('click', () => {
    if (clubSearchInput) clubSearchInput.value = '';
    currentSearch = '';
    clearSearchBtn.style.display = 'none';
    renderClubs();
  });
}

if (resetFilterBtn) {
  resetFilterBtn.addEventListener('click', () => {
    currentCategory = 'All';
    currentSearch = '';
    if (clubSearchInput) clubSearchInput.value = '';
    if (clearSearchBtn) clearSearchBtn.style.display = 'none';
    document.querySelectorAll('.cat-pill').forEach(p => {
      p.classList.toggle('active', p.dataset.category === 'All');
    });
    renderClubs();
  });
}

// Map Modal Controls
const mapModalCloseBtn = document.getElementById('mapModalCloseBtn');
const tabMapBtn = document.getElementById('tabMapBtn');
const headerMapBtn = document.getElementById('headerMapBtn');

function openMapModal() {
  if (mapModal) mapModal.style.display = 'flex';
}

function closeMapModal() {
  if (mapModal) mapModal.style.display = 'none';
}

if (tabMapBtn) tabMapBtn.addEventListener('click', openMapModal);
if (headerMapBtn) headerMapBtn.addEventListener('click', openMapModal);
if (mapModalCloseBtn) mapModalCloseBtn.addEventListener('click', closeMapModal);
if (mapModal) {
  mapModal.addEventListener('click', (e) => {
    if (e.target === mapModal) closeMapModal();
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && mapModal && mapModal.style.display === 'flex') {
    closeMapModal();
  }
});

// Global click delegation for cards, map, and suggestions
document.addEventListener('click', (e) => {
  if (e.target.closest('.open-map-modal-btn')) {
    openMapModal();
    return;
  }

  const viewBtn = e.target.closest('.view-club-btn');
  if (viewBtn && viewBtn.dataset.clubId) {
    if (!clubsLoaded) {
      loadClubsDataIfNeeded().then(() => openClubModal(viewBtn.dataset.clubId));
    } else {
      openClubModal(viewBtn.dataset.clubId);
    }
    return;
  }

  const askBtn = e.target.closest('.ask-club-btn');
  if (askBtn && askBtn.dataset.clubName) {
    switchView('chat');
    sendMessage(`Tell me about ${askBtn.dataset.clubName}`);
    return;
  }

  const promptChip = e.target.closest('.prompt-chip');
  if (promptChip && promptChip.dataset.q) {
    switchView('chat');
    sendMessage(promptChip.dataset.q);
    return;
  }
});