const form = document.getElementById('loginForm');
const prnInput = document.getElementById('prn');
const nameInput = document.getElementById('studentName');
const prnError = document.getElementById('prnError');
const nameError = document.getElementById('nameError');

// If a session already exists, skip straight to chat.
if (sessionStorage.getItem('kitcoek_student_name')) {
  window.location.href = 'index.html';
}

function validatePRN(value){
  // Accepts alphanumeric PRNs, 6–15 characters. Adjust to match your college's actual PRN format.
  return /^[A-Za-z0-9]{6,15}$/.test(value.trim());
}

function validateName(value){
  return value.trim().length >= 2;
}

function setInvalid(input, errorEl, message){
  input.classList.add('invalid');
  errorEl.textContent = message;
}

function clearInvalid(input, errorEl){
  input.classList.remove('invalid');
  errorEl.textContent = '';
}

form.addEventListener('submit', (e) => {
  e.preventDefault();

  const prnValue = prnInput.value.trim();
  const nameValue = nameInput.value.trim();
  let hasError = false;

  if (!validatePRN(prnValue)){
    setInvalid(prnInput, prnError, 'Enter a valid PRN (letters/numbers, 6–15 characters).');
    hasError = true;
  } else {
    clearInvalid(prnInput, prnError);
  }

  if (!validateName(nameValue)){
    setInvalid(nameInput, nameError, 'Enter your full name.');
    hasError = true;
  } else {
    clearInvalid(nameInput, nameError);
  }

  if (hasError) return;

  // Store session info for the chat screen to read.
  sessionStorage.setItem('kitcoek_student_prn', prnValue);
  sessionStorage.setItem('kitcoek_student_name', nameValue);

  window.location.href = 'index.html';
});

// Clear the error state as the student starts fixing a field.
prnInput.addEventListener('input', () => clearInvalid(prnInput, prnError));
nameInput.addEventListener('input', () => clearInvalid(nameInput, nameError));