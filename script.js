const thread = document.getElementById('thread');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const suggestions = document.getElementById('suggestions');
const newChatBtn = document.getElementById('newChatBtn');
const historyList = document.getElementById('historyList');
const sidebarName = document.getElementById('sidebarName');
const sidebarPrn = document.getElementById('sidebarPrn');
const signOutLink = document.getElementById('signOutLink');

// ---- Student session (set on the login page) ----
const studentName = sessionStorage.getItem('kitcoek_student_name');
const studentPrn = sessionStorage.getItem('kitcoek_student_prn');

if (!studentName) {
  // No active session — send the student back to sign in.
  window.location.href = 'login.html';
}

sidebarName.textContent = studentName || 'Student';
sidebarPrn.textContent = studentPrn ? 'PRN ' + studentPrn : '';

signOutLink.addEventListener('click', () => {
  sessionStorage.removeItem('kitcoek_student_name');
  sessionStorage.removeItem('kitcoek_student_prn');
});

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

function sendMessage(text){
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

  // Simulated network delay — replace with a real API call (see comment block below)
  setTimeout(() => {
    removeTyping();
    addRow('bot', findReply(trimmed));
    sendBtn.disabled = false;
  }, 700 + Math.random() * 500);
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
  if (btn) sendMessage(btn.dataset.q);
});

newChatBtn.addEventListener('click', () => {
  thread.innerHTML = '';
  addRow('bot', `<p>New conversation started. What would you like to know?</p>`);
});

/*
  ---- Wiring to a real backend ----
  Replace findReply() + the setTimeout above with something like:

  async function getBotReply(userText){
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText })
    });
    const data = await res.json();
    return data.reply; // HTML or plain text from your server / LLM API
  }
*/