const thread = document.getElementById('thread');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const suggestions = document.getElementById('suggestions');
const newChatBtn = document.getElementById('newChatBtn');
const historyList = document.getElementById('historyList');
const sidebarName = document.getElementById('sidebarName');
const sidebarPrn = document.getElementById('sidebarPrn');
const signOutLink = document.getElementById('signOutLink');

// ---- Student session (set to default if not set) ----
let studentName = sessionStorage.getItem('kitcoek_student_name');
let studentPrn = sessionStorage.getItem('kitcoek_student_prn');

if (!studentName) {
  studentName = 'KITCOEK Student';
  studentPrn = '2024CS001';
  sessionStorage.setItem('kitcoek_student_name', studentName);
  sessionStorage.setItem('kitcoek_student_prn', studentPrn);
}

sidebarName.textContent = studentName || 'Student';
sidebarPrn.textContent = studentPrn ? 'PRN ' + studentPrn : '';

if (signOutLink) {
  signOutLink.addEventListener('click', (e) => {
    e.preventDefault();
    sessionStorage.removeItem('kitcoek_student_name');
    sessionStorage.removeItem('kitcoek_student_prn');
    location.reload();
  });
}


// Personalize the first greeting with the student's first name.
const firstName = studentName ? studentName.trim().split(' ')[0] : '';
const greetingBubble = document.querySelector('.thread .row.bot .bubble p');
if (greetingBubble && firstName) {
  greetingBubble.textContent = `Hi ${firstName}, I'm the KITCOEK Assistant. Ask me about registration, financial aid, hostel, or anything else about campus — or pick a topic below to start.`;
}

// ---- Canned knowledge base (swap this for a real API call — see bottom) ----
const knowledge = [
  { keys: ['financial aid','fafsa','scholarship','tuition','fee'],
    reply: `<p>Scholarship and fee-related applications for next term are due <strong>November 15</strong>. You'll need:</p>
            <ul><li>Completed application form</li><li>Income certificate / relevant documents</li><li>Proof of enrollment</li></ul>
            <p>You can start or check your application in the Student Portal under "Financial Aid."</p>` },
  { keys: ['register','registration','add','drop','course','class','subject'],
    reply: `<p>Course registration opens on a rolling schedule by semester. To add or drop a subject:</p>
            <ul><li>Go to Student Portal → Registration</li><li>Search by subject code or department</li><li>Drop period ends two weeks into the term</li></ul>` },
  { keys: ['library','hours'],
    reply: `<p>The central library is open <strong>8am–8pm</strong> Monday–Saturday. Extended hours apply during exam weeks.</p>` },
  { keys: ['event','events','happening','activities','fest'],
    reply: `<p>This week on campus:</p>
            <ul><li>Technical fest prep meeting — Wednesday, Seminar Hall, 3pm</li><li>Cultural evening — Friday, Main Ground, 6pm</li><li>Placement drive orientation — Saturday, Auditorium, 10am</li></ul>` },
  { keys: ['hostel','room','accommodation'],
    reply: `<p>Hostel applications are reviewed in the order they're submitted. You can check your status anytime under Student Portal → Hostel. Room allotments for next term go out three weeks before the semester starts.</p>` },
  { keys: ['admission','apply','eligibility'],
    reply: `<p>Admissions are handled through the centralized counseling process. You'll need your entrance exam scorecard, 10th/12th mark sheets, and category certificate (if applicable). Visit the Admissions cell for the current cutoff details.</p>` },
  { keys: ['placement','company','recruitment','job'],
    reply: `<p>The Training &amp; Placement cell coordinates all campus recruitment drives. Keep your resume and academic records updated on the placement portal to stay eligible for upcoming drives.</p>` },
  { keys: ['hello','hi','hey'],
    reply: `<p>Hello! What can I help you find — courses, financial aid, hostel, placements, or something else?</p>` }
];

function findReply(text){
  const lower = text.toLowerCase();
  const match = knowledge.find(k => k.keys.some(word => lower.includes(word)));
  if (match) return match.reply;
  return `<p>I don't have a specific answer for that yet, but I can connect you with the right department, or you can try asking about financial aid, course registration, hostel, placements, or campus events.</p>`;
}

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

// ---- Dynamic suggestions update ----
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

async function sendMessage(text){
  const trimmed = text.trim();
  if (!trimmed) return;

  addRow('user', `<p>${escapeHtml(trimmed)}</p>`);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  // add to sidebar history (front of list)
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

    // Append navigation map card if present
    if (data.location_details) {
      const loc = data.location_details;
      botHtml += `
        <div class="nav-box">
          <p><strong>Campus Location:</strong> ${escapeHtml(loc.building)} — ${escapeHtml(loc.floor)}</p>
          ${loc.landmark ? `<p style="font-size:12px; margin-top:2px;"><em>Landmark: ${escapeHtml(loc.landmark)}</em></p>` : ''}
          ${data.map_url ? `<a href="${data.map_url}" target="_blank" class="map-link-btn">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            Open Campus Map
          </a>` : ''}
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

function escapeHtml(str){
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
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
      sendMessage(q);
    }
  });
}

newChatBtn.addEventListener('click', () => {
  thread.innerHTML = '';
  addRow('bot', `<p>New conversation started. What would you like to know?</p>`);
});