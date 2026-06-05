const express = require('express');
const session = require('express-session');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const PASSWORD = process.env.APP_PASSWORD || 'beers';
const dataDir = process.env.DATA_DIR || path.join(__dirname, 'data');
const DATA_FILE = path.join(dataDir, 'beers.json');

if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });

function readData() {
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  } catch {
    return { people: [], nextId: 1 };
  }
}

function writeData(data) {
  const tmp = DATA_FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, DATA_FILE);
}

app.use(express.json());
app.use(session({
  secret: process.env.SESSION_SECRET || 'beer-secret-please-change-in-production',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 12 * 60 * 60 * 1000 }
}));
app.use(express.static(path.join(__dirname, 'public')));

const auth = (req, res, next) => {
  if (req.session?.authenticated) return next();
  res.status(401).json({ error: 'Unauthorized' });
};

app.post('/api/auth', (req, res) => {
  if (req.body.password === PASSWORD) {
    req.session.authenticated = true;
    return res.json({ ok: true });
  }
  res.status(401).json({ error: 'Wrong password' });
});

app.post('/api/logout', (req, res) => {
  req.session.destroy(() => res.json({ ok: true }));
});

app.get('/api/people', auth, (req, res) => {
  res.json(readData().people);
});

app.post('/api/people', auth, (req, res) => {
  const name = (req.body.name || '').trim().slice(0, 30);
  if (!name) return res.status(400).json({ error: 'Name required' });
  const data = readData();
  const person = { id: data.nextId++, name, count: 0 };
  data.people.push(person);
  writeData(data);
  res.json(person);
});

app.delete('/api/people/:id', auth, (req, res) => {
  const id = parseInt(req.params.id, 10);
  const data = readData();
  data.people = data.people.filter(p => p.id !== id);
  writeData(data);
  res.json({ ok: true });
});

app.post('/api/people/:id/drink', auth, (req, res) => {
  const id = parseInt(req.params.id, 10);
  const data = readData();
  const person = data.people.find(p => p.id === id);
  if (!person) return res.status(404).json({ error: 'Not found' });
  person.count += 1;
  writeData(data);
  res.json(person);
});

app.post('/api/reset', auth, (req, res) => {
  const data = readData();
  data.people.forEach(p => { p.count = 0; });
  writeData(data);
  res.json({ ok: true });
});

app.listen(PORT, () => console.log(`Beer counter running on http://localhost:${PORT}`));
