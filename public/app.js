let pollInterval = null;
let localCounts = {};

// ─── Auth ──────────────────────────────────────────────────

async function login() {
  const passwordEl = document.getElementById('password-input');
  const errorEl = document.getElementById('login-error');
  errorEl.textContent = '';

  try {
    const res = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: passwordEl.value }),
    });

    if (res.ok) {
      passwordEl.value = '';
      showApp();
    } else {
      errorEl.textContent = 'Wrong password, try again!';
      passwordEl.value = '';
      passwordEl.focus();
    }
  } catch {
    errorEl.textContent = 'Connection error — is the server running?';
  }
}

async function logout() {
  await fetch('/api/logout', { method: 'POST' }).catch(() => {});
  clearInterval(pollInterval);
  pollInterval = null;
  localCounts = {};
  document.getElementById('app').classList.add('hidden');
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('password-input').focus();
}

// ─── Boot ──────────────────────────────────────────────────

async function boot() {
  // Check if we already have a valid session
  const res = await fetch('/api/people').catch(() => null);
  if (res && res.ok) {
    showApp(await res.json());
  } else {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('password-input').focus();
  }
}

function showApp(initialPeople = null) {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');

  if (initialPeople) {
    renderPeople(initialPeople);
  } else {
    loadPeople();
  }

  if (!pollInterval) {
    pollInterval = setInterval(loadPeople, 2000);
  }
}

// ─── Data ──────────────────────────────────────────────────

async function loadPeople() {
  const res = await fetch('/api/people').catch(() => null);
  if (!res) return;
  if (res.status === 401) {
    clearInterval(pollInterval);
    pollInterval = null;
    document.getElementById('app').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
    return;
  }
  if (res.ok) renderPeople(await res.json());
}

async function addPerson() {
  const input = document.getElementById('new-name');
  const name = input.value.trim();
  if (!name) { input.focus(); return; }

  const res = await fetch('/api/people', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });

  if (res.ok) {
    input.value = '';
    loadPeople();
  }
}

async function deletePerson(id, event) {
  event.stopPropagation();
  if (!confirm('Remove this person?')) return;
  await fetch(`/api/people/${id}`, { method: 'DELETE' });
  delete localCounts[id];
  loadPeople();
}

async function addDrink(id, cardEl) {
  // Optimistically update the count in the DOM immediately
  localCounts[id] = (localCounts[id] || 0) + 1;
  const countEl = cardEl.querySelector('.card-count');
  if (countEl) {
    countEl.textContent = localCounts[id];
    countEl.classList.remove('pop');
    void countEl.offsetWidth; // reflow to restart animation
    countEl.classList.add('pop');
  }

  // Tap animation
  cardEl.classList.remove('tapping');
  void cardEl.offsetWidth;
  cardEl.classList.add('tapping');

  // +1 floater
  showPlusOne(cardEl);

  const res = await fetch(`/api/people/${id}/drink`, { method: 'POST' });
  if (res.ok) {
    const person = await res.json();
    localCounts[id] = person.count;
    if (countEl) countEl.textContent = person.count;
  }
}

async function resetAll() {
  if (!confirm('Reset all beer counts to 0?')) return;
  await fetch('/api/reset', { method: 'POST' });
  localCounts = {};
  loadPeople();
}

// ─── Render ────────────────────────────────────────────────

function renderPeople(people) {
  const grid = document.getElementById('people-grid');

  if (people.length === 0) {
    grid.innerHTML = `
      <div class="empty-state">
        <span class="empty-emoji">🍻</span>
        <p>Add your friends below to get started!</p>
      </div>`;
    return;
  }

  // Sync localCounts with server truth (only for non-pending updates)
  for (const p of people) {
    if (localCounts[p.id] === undefined) {
      localCounts[p.id] = p.count;
    }
  }

  // Build a map of existing cards for in-place DOM updates
  const existing = {};
  grid.querySelectorAll('.person-card[data-id]').forEach(el => {
    existing[el.dataset.id] = el;
  });

  const ids = new Set(people.map(p => String(p.id)));

  // Remove cards for deleted people
  for (const [id, el] of Object.entries(existing)) {
    if (!ids.has(id)) el.remove();
  }

  // Add or update cards
  for (let i = 0; i < people.length; i++) {
    const p = people[i];
    const displayCount = localCounts[p.id] ?? p.count;

    if (existing[p.id]) {
      // Update count if changed and no local optimistic update is pending
      const countEl = existing[p.id].querySelector('.card-count');
      if (countEl && !existing[p.id].classList.contains('tapping')) {
        countEl.textContent = displayCount;
        localCounts[p.id] = p.count;
      }
    } else {
      // Create new card
      const card = createCard(p, displayCount);
      // Insert at correct position
      const ref = grid.children[i];
      if (ref) {
        grid.insertBefore(card, ref);
      } else {
        grid.appendChild(card);
      }
      existing[p.id] = card;
    }
  }
}

function createCard(person, count) {
  const card = document.createElement('div');
  card.className = 'person-card';
  card.dataset.id = person.id;
  card.innerHTML = `
    <button class="delete-btn" title="Remove ${escapeHtml(person.name)}" onclick="deletePerson(${person.id}, event)">✕</button>
    <span class="card-glass">🍺</span>
    <span class="card-name">${escapeHtml(person.name)}</span>
    <span class="card-count">${count}</span>
    <span class="card-beers-label">beers</span>
  `;
  card.addEventListener('click', () => addDrink(person.id, card));
  card.addEventListener('animationend', () => card.classList.remove('tapping'));
  return card;
}

function showPlusOne(card) {
  const el = document.createElement('div');
  el.className = 'plus-one';
  el.textContent = '+1';
  card.appendChild(el);
  el.addEventListener('animationend', () => el.remove());
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ─── Init ──────────────────────────────────────────────────

boot();
