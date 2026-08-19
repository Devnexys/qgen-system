'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  currentTab: 'text',
  difficulty: 'medium',
  sessionId: null,
  questions: [],
  quiz: { index: 0, score: 0, answered: false }
};

const SAMPLE_TEXT = `The discovery of penicillin by Alexander Fleming in 1928 marked a revolutionary moment in medical history. Fleming noticed that a mold, Penicillium notatum, had contaminated one of his petri dishes and was killing the surrounding bacteria. This accidental observation led to the development of the first antibiotic, which saved millions of lives during World War II and beyond.

The Industrial Revolution, which began in Britain around 1760, fundamentally transformed manufacturing and society. Steam-powered machines replaced manual labor, leading to mass production in factories. This period saw the invention of the steam engine by James Watt, which became the driving force behind railways, ships, and industrial machinery.

Albert Einstein published his theory of special relativity in 1905, fundamentally changing our understanding of space, time, and energy. The famous equation E=mc² expresses the equivalence of mass and energy, where c represents the speed of light in a vacuum. Einstein was awarded the Nobel Prize in Physics in 1921, not for relativity, but for his explanation of the photoelectric effect.

The Amazon Rainforest spans approximately 5.5 million square kilometers across nine countries in South America, with Brazil containing about 60 percent of it. It is home to an estimated 390 billion individual trees representing 16,000 species. The Amazon River discharges about 20 percent of all freshwater that enters the world's oceans.

The French Revolution, which began in 1789, was a period of radical political and social transformation in France. The storming of the Bastille prison on July 14, 1789, became a symbol of the uprising against the monarchy and aristocracy. The revolution led to the Declaration of the Rights of Man and of the Citizen.`;

// ── Helpers ───────────────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

function showToast(msg, type = 'info', duration = 4000) {
  const container = $('toastContainer');
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'none';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100px)';
    toast.style.transition = 'all .3s';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function setLoading(show, step = '', progress = 0) {
  $('loadingState').style.display = show ? 'flex' : 'none';
  $('generateBtn').disabled = show;
  if (show) {
    $('loadingStep').textContent = step;
    $('loadingBar').style.width = progress + '%';
  }
}

function animateProgress(steps) {
  let i = 0;
  const interval = setInterval(() => {
    if (i >= steps.length) { clearInterval(interval); return; }
    $('loadingStep').textContent = steps[i].text;
    $('loadingBar').style.width = steps[i].pct + '%';
    i++;
  }, steps[0]?.delay || 900);
  return interval;
}

// ── Tab Switching ─────────────────────────────────────────────────────────────
function switchTab(tab) {
  state.currentTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.id === 'tab' + tab.charAt(0).toUpperCase() + tab.slice(1));
    b.setAttribute('aria-selected', b.classList.contains('active'));
  });
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const tabEl = $(tab + 'Tab');
  if (tabEl) tabEl.classList.add('active');
}

function loadSample() {
  switchTab('text');
  const ta = $('textInput');
  ta.value = SAMPLE_TEXT;
  updateCharCount(ta);
  showToast('Sample text loaded — click Generate!', 'success');
  // Click the text tab button too
  $('tabText').classList.add('active');
  $('tabSample').classList.remove('active');
}

function showSection(section) {
  if (section === 'quiz') {
    if (!state.questions.length) { showToast('Generate questions first!', 'info'); return; }
    startQuiz();
  } else {
    $('quizSection').style.display = 'none';
    $('generate').scrollIntoView({ behavior: 'smooth' });
  }
}

// ── Character Count ───────────────────────────────────────────────────────────
function updateCharCount(ta) {
  const count = ta.value.length;
  $('charCount').textContent = `${count.toLocaleString()} characters`;
}

function clearText() {
  $('textInput').value = '';
  updateCharCount($('textInput'));
}

// ── Numeric Input ─────────────────────────────────────────────────────────────
function adjustNum(delta) {
  const input = $('numQuestions');
  const val = Math.min(20, Math.max(1, parseInt(input.value || 5) + delta));
  input.value = val;
}

// ── Difficulty ────────────────────────────────────────────────────────────────
function setDifficulty(level) {
  state.difficulty = level;
  ['easy', 'medium', 'hard'].forEach(d => {
    const btn = $('diff' + d.charAt(0).toUpperCase() + d.slice(1));
    btn.classList.toggle('active', d === level);
    btn.setAttribute('aria-pressed', d === level);
  });
}

// ── File Upload ───────────────────────────────────────────────────────────────
function handleDragOver(e) {
  e.preventDefault();
  $('dropZone').classList.add('drag-over');
}
function handleDragLeave() { $('dropZone').classList.remove('drag-over'); }
function handleDrop(e) {
  e.preventDefault();
  $('dropZone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) applyFile(file);
}
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) applyFile(file);
}
function applyFile(file) {
  const allowed = ['pdf', 'docx', 'txt'];
  const ext = file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showToast(`Unsupported file type: .${ext}`, 'error');
    return;
  }
  $('fileName').textContent = file.name;
  $('fileSize').textContent = formatBytes(file.size);
  $('filePreview').style.display = 'flex';
  $('dropZone').style.display = 'none';
  state.uploadedFile = file;
  showToast(`${file.name} ready`, 'success', 2000);
}
function removeFile() {
  state.uploadedFile = null;
  $('fileInput').value = '';
  $('filePreview').style.display = 'none';
  $('dropZone').style.display = 'block';
}
function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}

// ── Generate Questions ────────────────────────────────────────────────────────
async function generateQuestions() {
  const numQ = parseInt($('numQuestions').value) || 5;
  const useT5 = $('useT5').checked;

  setLoading(true, 'Starting AI pipeline...', 5);
  $('resultsPanel').style.display = 'none';
  $('quizSection').style.display = 'none';

  const steps = [
    { text: 'Extracting and cleaning text...', pct: 15, delay: 800 },
    { text: 'Running NLP analysis (spaCy)...', pct: 30, delay: 1200 },
    { text: 'Identifying key concepts and entities...', pct: 45, delay: 1000 },
    { text: 'Generating questions with T5...', pct: 60, delay: 1500 },
    { text: 'Creating semantic distractors...', pct: 75, delay: 1200 },
    { text: 'Validating with RoBERTa QA model...', pct: 88, delay: 1400 },
    { text: 'Scoring and ranking questions...', pct: 95, delay: 800 },
  ];
  let stepIdx = 0;
  const progressInterval = setInterval(() => {
    if (stepIdx >= steps.length) { clearInterval(progressInterval); return; }
    $('loadingStep').textContent = steps[stepIdx].text;
    $('loadingBar').style.width = steps[stepIdx].pct + '%';
    stepIdx++;
  }, 950);

  try {
    let data;
    if (state.currentTab === 'file' && state.uploadedFile) {
      data = await uploadFile(state.uploadedFile, numQ, useT5);
    } else {
      const text = $('textInput').value.trim();
      if (!text || text.length < 50) {
        showToast('Please enter at least 50 characters of educational text.', 'error');
        setLoading(false); clearInterval(progressInterval); return;
      }
      data = await generateFromText(text, numQ, useT5);
    }

    clearInterval(progressInterval);
    $('loadingBar').style.width = '100%';

    state.sessionId = data.session_id;
    state.questions = data.questions || [];

    setTimeout(() => {
      setLoading(false);
      renderResults(data);
    }, 400);

  } catch (err) {
    clearInterval(progressInterval);
    setLoading(false);
    showToast(err.message || 'Generation failed. Check if backend is running.', 'error', 6000);
  }
}

async function generateFromText(text, numQ, useT5) {
  const res = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, num_questions: numQ, difficulty: state.difficulty, use_t5: useT5 })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error: ${res.status}`);
  }
  return res.json();
}

async function uploadFile(file, numQ, useT5) {
  const form = new FormData();
  form.append('file', file);
  form.append('num_questions', numQ);
  form.append('difficulty', state.difficulty);
  form.append('use_t5', useT5);
  const res = await fetch('/api/upload', { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error: ${res.status}`);
  }
  return res.json();
}

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(data) {
  const { questions, total_generated, topic, message } = data;

  $('topicBadge').textContent = topic || 'General';
  $('resultsStats').textContent =
    `${total_generated} question${total_generated !== 1 ? 's' : ''} generated · Difficulty: ${state.difficulty}`;

  const list = $('questionsList');
  list.innerHTML = '';

  if (!questions || questions.length === 0) {
    list.innerHTML = `<div class="glass-card" style="text-align:center;padding:40px;color:var(--muted)">
      <p style="font-size:1.5rem;margin-bottom:12px">😕</p>
      <p>${message || 'No questions could be generated. Try adding more factual content.'}</p>
    </div>`;
    $('resultsPanel').style.display = 'block';
    showToast('No questions generated. Try more educational text.', 'info');
    return;
  }

  questions.forEach(q => list.appendChild(buildQuestionCard(q)));
  $('resultsPanel').style.display = 'block';
  $('resultsPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  showToast(`${total_generated} questions ready!`, 'success');
}

function buildQuestionCard(q) {
  const card = document.createElement('div');
  card.className = 'question-card';
  card.setAttribute('role', 'listitem');

  const confPct = Math.round((q.confidence_score || 0) * 100);
  const diffClass = `tag-difficulty-${q.difficulty || 'medium'}`;
  const methodLabel = q.generation_method === 't5' ? '🤖 T5' : '📋 Rule-based';
  const optionLabels = ['A', 'B', 'C', 'D'];

  const optionsHtml = (q.options || []).map((opt, i) => {
    const isCorrect = opt === q.correct_answer;
    return `<div class="option-item${isCorrect ? ' correct' : ''}">
      <span class="option-label">${optionLabels[i] || i + 1}</span>
      <span>${escHtml(opt)}</span>
      ${isCorrect ? '<span class="correct-indicator">✓ Correct</span>' : ''}
    </div>`;
  }).join('');

  card.innerHTML = `
    <div class="q-header" onclick="toggleCard(this)" role="button" tabindex="0"
         aria-expanded="false" onkeydown="if(event.key==='Enter'||event.key===' ')toggleCard(this)">
      <div class="q-num">${q.id}</div>
      <div class="q-meta">
        <p class="q-text">${escHtml(q.question)}</p>
        <div class="q-tags">
          <span class="q-tag ${diffClass}">${(q.difficulty || 'medium').toUpperCase()}</span>
          <span class="q-tag tag-method">${methodLabel}</span>
          <span class="confidence-badge">
            <span class="conf-bar"><span class="conf-fill" style="width:${confPct}%"></span></span>
            ${confPct}% confidence
          </span>
        </div>
      </div>
      <svg class="q-expand-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </div>
    <div class="q-body">
      <div class="options-grid">${optionsHtml}</div>
      <div class="explanation-box">
        <p class="explanation-title">💡 Explanation</p>
        <p class="explanation-text">${escHtml(q.explanation || 'The correct answer is derived from the source passage.')}</p>
      </div>
      <div class="source-box">
        <p class="source-label">📄 Source Passage</p>
        ${escHtml(q.source_sentence || '')}
      </div>
    </div>`;

  return card;
}

function toggleCard(header) {
  const card = header.closest('.question-card');
  const expanded = card.classList.toggle('expanded');
  header.setAttribute('aria-expanded', expanded);
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Export ────────────────────────────────────────────────────────────────────
async function exportFile(format) {
  if (!state.sessionId) { showToast('Generate questions first.', 'info'); return; }
  try {
    const res = await fetch(`/api/export/${format}/${state.sessionId}`);
    if (!res.ok) throw new Error('Export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mcqs_${state.sessionId}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`Exported as ${format.toUpperCase()}!`, 'success');
  } catch (e) {
    showToast('Export failed: ' + e.message, 'error');
  }
}

// ── Quiz Mode ─────────────────────────────────────────────────────────────────
function startQuiz() {
  if (!state.questions.length) { showToast('No questions to quiz!', 'info'); return; }
  state.quiz = { index: 0, score: 0, answered: false };
  $('resultsPanel').style.display = 'none';
  const qs = $('quizSection');
  qs.style.display = 'block';
  $('quizResults').style.display = 'none';
  $('quizQuestionArea').style.display = 'block';
  $('quizTotal').textContent = state.questions.length;
  qs.scrollIntoView({ behavior: 'smooth' });
  renderQuizQuestion();
}

function renderQuizQuestion() {
  const { index } = state.quiz;
  const q = state.questions[index];
  if (!q) { showQuizResults(); return; }

  state.quiz.answered = false;
  $('quizCurrent').textContent = index + 1;
  $('quizScore').textContent = state.quiz.score;
  $('quizProgressFill').style.width = ((index / state.questions.length) * 100) + '%';
  $('quizFeedback').style.display = 'none';
  $('quizNextBtn').style.display = 'none';

  const optionLabels = ['A', 'B', 'C', 'D'];
  const optionsHtml = (q.options || []).map((opt, i) =>
    `<button class="quiz-option" onclick="answerQuiz(this, '${escAttr(opt)}', '${escAttr(q.correct_answer)}')"
      data-answer="${escAttr(opt)}">
      <span class="quiz-opt-label">${optionLabels[i]}</span>
      ${escHtml(opt)}
    </button>`
  ).join('');

  $('quizQuestionArea').innerHTML = `
    <p class="quiz-question-text">Q${index + 1}. ${escHtml(q.question)}</p>
    <div class="quiz-options">${optionsHtml}</div>`;
}

function answerQuiz(btn, selected, correct) {
  if (state.quiz.answered) return;
  state.quiz.answered = true;

  const allBtns = btn.closest('.quiz-options').querySelectorAll('.quiz-option');
  allBtns.forEach(b => {
    b.disabled = true;
    if (b.dataset.answer === correct) b.classList.add(selected === correct ? 'selected-correct' : 'reveal-correct');
  });

  const isCorrect = selected === correct;
  if (isCorrect) state.quiz.score++;

  btn.classList.add(isCorrect ? 'selected-correct' : 'selected-wrong');

  const feedback = $('quizFeedback');
  const q = state.questions[state.quiz.index];
  feedback.className = `quiz-feedback ${isCorrect ? 'correct-fb' : 'wrong-fb'}`;
  feedback.innerHTML = `
    <strong>${isCorrect ? '✓ Correct!' : '✕ Incorrect'}</strong><br/>
    ${isCorrect ? '' : `Correct answer: <strong>${escHtml(correct)}</strong><br/>`}
    ${escHtml(q.explanation || '')}`;
  feedback.style.display = 'block';
  $('quizNextBtn').style.display = 'block';
  $('quizScore').textContent = state.quiz.score;
}

function nextQuizQuestion() {
  state.quiz.index++;
  if (state.quiz.index >= state.questions.length) { showQuizResults(); return; }
  renderQuizQuestion();
}

function showQuizResults() {
  $('quizQuestionArea').style.display = 'none';
  $('quizFeedback').style.display = 'none';
  $('quizNextBtn').style.display = 'none';
  $('quizProgressFill').style.width = '100%';

  const total = state.questions.length;
  const score = state.quiz.score;
  const pct = Math.round((score / total) * 100);

  $('quizScoreCircle').textContent = `${pct}%`;
  let title, sub;
  if (pct >= 80) { title = '🎉 Excellent!'; sub = `You scored ${score}/${total}. Outstanding performance!`; }
  else if (pct >= 60) { title = '👍 Good Job!'; sub = `You scored ${score}/${total}. Keep practicing!`; }
  else { title = '📚 Keep Learning!'; sub = `You scored ${score}/${total}. Review the material and try again.`; }

  $('quizResultTitle').textContent = title;
  $('quizResultSub').textContent = sub;
  $('quizResults').style.display = 'block';
}

function restartQuiz() { startQuiz(); }

function exitQuiz() {
  $('quizSection').style.display = 'none';
  if (state.questions.length) $('resultsPanel').style.display = 'block';
}

function escAttr(str) {
  return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fetch('/api/health')
    .then(r => r.json())
    .then(() => showToast('Backend connected ✓', 'success', 2500))
    .catch(() => showToast('Backend not reachable — start the server!', 'error', 6000));
});
