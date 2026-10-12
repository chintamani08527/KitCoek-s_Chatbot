const thread = document.getElementById('thread');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const suggestions = document.getElementById('suggestions');
const newChatBtn = document.getElementById('newChatBtn');
const historyList = document.getElementById('historyList');
const sidebarName = document.getElementById('sidebarName');
const sidebarPrn = document.getElementById('sidebarPrn');
const signOutLink = document.getElementById('signOutLink');

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

// ---- Student session (set to default if not set) ----
let studentName = sessionStorage.getItem('kitcoek_student_name');
let studentPrn = sessionStorage.getItem('kitcoek_student_prn');

if (!studentName) {
  studentName = 'KITCOEK Student';
  studentPrn = '2024CS001';
  sessionStorage.setItem('kitcoek_student_name', studentName);
  sessionStorage.setItem('kitcoek_student_prn', studentPrn);
}

if (sidebarName) sidebarName.textContent = studentName || 'Student';
if (sidebarPrn) sidebarPrn.textContent = studentPrn ? 'PRN ' + studentPrn : '';

if (signOutLink) {
  signOutLink.addEventListener('click', (e) => {
    e.preventDefault();
    sessionStorage.removeItem('kitcoek_student_name');
    sessionStorage.removeItem('kitcoek_student_prn');
    location.reload();
  });
}

// Personalize the first greeting with the student's first name
const firstName = studentName ? studentName.trim().split(' ')[0] : '';
const greetingBubble = document.querySelector('.thread .row.bot .bubble p');
if (greetingBubble && firstName) {
  greetingBubble.innerHTML = `Hi ${escapeHtml(firstName)}, I'm the KITCOEK Assistant. Ask me about registration, examinations, syllabus, or any of our <strong>18 Official Student Clubs</strong> (ISTE, E-Cell, SDC, Cultural, NSS, and more) — or pick a topic below to start.`;
}

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

// ---- Chat Functions ----
function addRow(role, html){
  const row = document.createElement('div');
  row.className = 'row ' + role;
  row.innerHTML = `
    <div class="avatar">${role === 'bot' ? 'K' : 'You'.slice(0,1)}</div>
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
  row.innerHTML = `<div class="avatar">K</div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
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

async function sendMessage(text){
  const trimmed = text.trim();
  if (!trimmed) return;

  addRow('user', `<p>${escapeHtml(trimmed)}</p>`);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  // Add to sidebar history
  const li = document.createElement('li');
  li.textContent = trimmed.length > 34 ? trimmed.slice(0,34) + '…' : trimmed;
  historyList.prepend(li);

  showTyping();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: trimmed,
        session_id: 'kitcoek_session',
        student_prn: studentPrn,
        student_name: studentName
      })
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const data = await response.json();
    removeTyping();

    // Construct response HTML
    let botHtml = data.reply;

    // Append club preview card if present in response
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

    // Append navigation map card if present
    if (data.location_details) {
      const loc = data.location_details;
      botHtml += `
        <div class="nav-box">
          <p><strong>Campus Location:</strong> ${escapeHtml(loc.building)} — ${escapeHtml(loc.floor)}</p>
          ${loc.landmark ? `<p style="font-size:12px; margin-top:2px;"><em>Landmark: ${escapeHtml(loc.landmark)}</em></p>` : ''}
          ${loc.room_number ? `<p style="font-size:12px; margin-top:2px;"><strong>Block / Rooms:</strong> ${escapeHtml(loc.room_number)}</p>` : ''}
          <div class="map-thumbnail-container open-map-modal-btn" title="Click to open Aerial Campus Map">
            <img src="/api/locations/map" alt="Aerial Campus Map Preview">
            <div class="map-thumbnail-overlay">
              <span>🗺️ Official Aerial Campus Map (Tap to view)</span>
              <span>🔍 Zoom</span>
            </div>
          </div>
          <div style="margin-top:8px; display:flex; gap:8px;">
            <button class="map-link-btn open-map-modal-btn" type="button">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
              View Aerial Map
            </button>
            <a href="/api/locations/map" target="_blank" class="map-link-btn" style="background:#fff; color:var(--ink); border:1px solid var(--hairline);">
              ↗ Open in Tab
            </a>
          </div>
        </div>
      `;
    }

    // Append Student Portal & LMS box if portal_url is present
    if (data.portal_url) {
      botHtml += `
        <div class="nav-box" style="border-left: 3px solid var(--pine); background: #f4fbf9; margin-top:10px;">
          <p><strong>KITCOEK Student Portal (vMedulife) &amp; LMS:</strong></p>
          <p style="font-size:12.5px; color:var(--text-muted); margin-top:2px; line-height:1.45;">
            Access semester examination results, SGPA/CGPA grade cards, LMS course notes, and attendance tracking.
          </p>
          <a href="${data.portal_url}" target="_blank" class="map-link-btn" style="background:var(--pine); color:#fff; display:inline-flex; align-items:center; gap:6px; margin-top:6px;">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            Open vMedulife Student Portal ↗
          </a>
        </div>
      `;
    }

    // Append Student Notes card if notes_url is present
    if (data.notes_url) {
      botHtml += `
        <div class="nav-box" style="border-left: 3px solid var(--gold); background: #fdfaf3; margin-top:10px;">
          <p><strong>KITCOEK Subject &amp; Handwritten Notes:</strong></p>
          <p style="font-size:12.5px; color:var(--text-muted); margin-top:2px; line-height:1.45;">
            Access verified PDF notes for Statistical Methods (Unit 4: Analysis of Variance), SPS (Unit 3), and department study materials.
          </p>
          <div style="margin-top:6px; display:flex; flex-wrap:wrap; gap:8px;">
            <a href="${data.notes_url}" target="_blank" class="map-link-btn" style="background:var(--ink); color:var(--gold); display:inline-flex; align-items:center; gap:6px;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              📄 Open Notes PDF / Folder ↗
            </a>
            <a href="https://drive.google.com/drive/folders/1_1mxw4T2BNFCYFOoolsfAmZi8zWvv1Hy" target="_blank" class="map-link-btn" style="background:#fff; color:var(--ink); border:1px solid var(--hairline); display:inline-flex; align-items:center; gap:6px;">
              📁 View All Notes in Drive
            </a>
          </div>
        </div>
      `;
    }

    // Append Timetable card if timetable_url is present
    if (data.timetable_url) {
      botHtml += `
        <div class="nav-box" style="border-left: 3px solid #2563eb; background: #f4f7fe; margin-top:10px;">
          <p><strong>KITCOEK Class &amp; Department Timetables:</strong></p>
          <p style="font-size:12.5px; color:var(--text-muted); margin-top:2px; line-height:1.45;">
            Access class schedules for CSBS (SY, TY, Final Year) and other institute department timetables.
          </p>
          <div style="margin-top:6px; display:flex; flex-wrap:wrap; gap:8px;">
            <a href="${data.timetable_url}" target="_blank" class="map-link-btn" style="background:#2563eb; color:#fff; display:inline-flex; align-items:center; gap:6px;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              📅 Open Timetable File ↗
            </a>
            <a href="https://drive.google.com/drive/folders/1Pi-i10qYtu9LQkhzhIMXQOtOa8LLCKZT" target="_blank" class="map-link-btn" style="background:#fff; color:var(--ink); border:1px solid var(--hairline); display:inline-flex; align-items:center; gap:6px;">
              📁 View Timetables Drive Folder
            </a>
          </div>
        </div>
      `;
    }

    // Append source citations if available
    if (data.sources && data.sources.length > 0) {
      const tags = data.sources
        .map(s => `<span class="citation-tag">${escapeHtml(s.document_name)} (${Math.round((s.score || 0)*100)}% match)</span>`)
        .join('');
      botHtml += `
        <div class="citations">
          <div class="citations-title">Sources &amp; References:</div>
          <div>${tags}</div>
        </div>
      `;
    }

    addRow('bot', botHtml);

    // Update follow-up questions
    if (data.follow_up_questions && data.follow_up_questions.length > 0) {
      renderSuggestions(data.follow_up_questions);
    }
    setTimeout(() => {
      thread.scrollTop = thread.scrollHeight;
    }, 50);
  } catch (err) {
    console.error('API Error:', err);
    removeTyping();
    addRow('bot', `<p style="color:#b91c1c;">Unable to reach KITCOEK backend server. Please verify backend is running on port 8000.</p>`);
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

suggestions.addEventListener('click', (e) => {
  const btn = e.target.closest('.chip');
  if (btn && btn.dataset.q) {
    sendMessage(btn.dataset.q);
  }
});

if (historyList) {
  historyList.addEventListener('click', (e) => {
    const li = e.target.closest('li');
    if (li && li.textContent) {
      const q = li.textContent.replace(/…$/, '').trim();
      switchView('chat');
      sendMessage(q);
    }
  });
}

newChatBtn.addEventListener('click', () => {
  switchView('chat');
  thread.innerHTML = '';
  addRow('bot', `<p>New conversation started. Ask me anything about KITCOEK academics, campus, or our 18 student clubs!</p>`);
});

// ---- Clubs Directory Functions ----
async function loadClubsDataIfNeeded() {
  if (clubsLoaded) return;
  try {
    const [clubsRes, catsRes] = await Promise.all([
      fetch('/api/clubs'),
      fetch('/api/clubs/categories')
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
          <p style="color:#b91c1c;">Unable to load clubs directory from backend. Please ensure the backend server is running.</p>
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
const mapModal = document.getElementById('mapModal');
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