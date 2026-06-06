/**
 * IT School LMS — Діагностичний скрипт
 * Запуск: node test-app.js
 * Потребує: запущений бекенд на http://localhost:8000
 *
 * Результат зберігається у test-results.json та test-results.log
 */

const http = require('http');
const https = require('https');
const fs = require('fs');

const BASE = process.env.API_BASE || 'http://localhost:8000';
const LOG_FILE = 'test-results.log';
const JSON_FILE = 'test-results.json';

// ─── Credentials ──────────────────────────────────────────────────────────────
const USERS = {
  student:  { email: 'student@test.com', password: 'test123' },
  teacher:  { email: 'teacher@test.com', password: 'test123' },
  admin:    { email: 'admin@test.com',   password: 'test123' },
};

// ─── State ────────────────────────────────────────────────────────────────────
const results = [];
let passed = 0, failed = 0, warned = 0;
const tokens = {};

// ─── Logger ───────────────────────────────────────────────────────────────────
const logLines = [];
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  logLines.push(line);
  console.log(msg);
}

function result(group, name, status, detail = '') {
  const emoji = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
  log(`  ${emoji} [${group}] ${name}${detail ? ': ' + detail : ''}`);
  results.push({ group, name, status, detail, ts: new Date().toISOString() });
  if (status === 'PASS') passed++;
  else if (status === 'FAIL') failed++;
  else warned++;
}

// ─── HTTP helper ──────────────────────────────────────────────────────────────
function req(method, path, body, token) {
  return new Promise((resolve, reject) => {
    const url = new URL(BASE + path);
    const isHttps = url.protocol === 'https:';
    const lib = isHttps ? https : http;
    const bodyStr = body ? JSON.stringify(body) : null;

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(bodyStr ? { 'Content-Length': Buffer.byteLength(bodyStr) } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    };

    const r = lib.request(options, res => {
      let data = '';
      res.on('data', c => (data += c));
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });
    r.on('error', reject);
    if (bodyStr) r.write(bodyStr);
    r.end();
  });
}

async function formPost(path, fields) {
  return new Promise((resolve, reject) => {
    const body = Object.entries(fields).map(([k,v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
    const url = new URL(BASE + path);
    const isHttps = url.protocol === 'https:';
    const lib = isHttps ? https : http;

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body),
      },
    };

    const r = lib.request(options, res => {
      let data = '';
      res.on('data', c => (data += c));
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, body: data }); }
      });
    });
    r.on('error', reject);
    r.write(body);
    r.end();
  });
}

// ─── Test sections ─────────────────────────────────────────────────────────────

async function testHealth() {
  log('\n── HEALTH CHECK ─────────────────────────────────────────────');
  try {
    const r = await req('GET', '/');
    result('Health', 'Backend reachable', r.status < 500 ? 'PASS' : 'FAIL', `HTTP ${r.status}`);
  } catch(e) {
    result('Health', 'Backend reachable', 'FAIL', e.message);
    log('  ⛔ Backend unreachable — решта тестів пропущена');
    return false;
  }

  try {
    const r = await req('GET', '/docs');
    result('Health', 'Swagger /docs', r.status === 200 ? 'PASS' : 'WARN', `HTTP ${r.status}`);
  } catch {}
  return true;
}

async function testAuth() {
  log('\n── AUTH ─────────────────────────────────────────────────────');
  for (const [role, creds] of Object.entries(USERS)) {
    try {
      const r = await formPost('/api/auth/login', { username: creds.email, password: creds.password });
      if (r.status === 200 && r.body.access_token) {
        tokens[role] = r.body.access_token;
        result('Auth', `Login as ${role}`, 'PASS');
      } else {
        result('Auth', `Login as ${role}`, 'FAIL', `HTTP ${r.status} — ${JSON.stringify(r.body).slice(0,120)}`);
      }
    } catch(e) {
      result('Auth', `Login as ${role}`, 'FAIL', e.message);
    }
  }

  // /me endpoints
  for (const role of Object.keys(tokens)) {
    const r = await req('GET', '/api/users/me', null, tokens[role]);
    result('Auth', `/me for ${role}`, r.status === 200 ? 'PASS' : 'FAIL',
      r.status === 200 ? `${r.body.full_name} (${r.body.role})` : `HTTP ${r.status}`);
  }
}

async function testStudentEndpoints() {
  const t = tokens.student;
  if (!t) { log('  ⛔ No student token — skip'); return; }
  log('\n── STUDENT ENDPOINTS ────────────────────────────────────────');

  const endpoints = [
    ['/api/student/courses',      'Student courses'],
    ['/api/student/grades',       'Student grades'],
    ['/api/student/assignments',  'Student assignments (alias)'],
    ['/api/assignments',          'Assignments list'],
    ['/api/courses',              'Course catalog'],
    ['/api/schedule',             'Schedule'],
  ];
  for (const [path, name] of endpoints) {
    try {
      const r = await req('GET', path, null, t);
      const ok = r.status === 200;
      const info = ok ? `${Array.isArray(r.body) ? r.body.length + ' items' : 'ok'}` : `HTTP ${r.status}`;
      result('Student', name, ok ? 'PASS' : 'FAIL', info);
    } catch(e) {
      result('Student', name, 'FAIL', e.message);
    }
  }

  // Submit assignment test (get first available assignment id)
  try {
    const aResp = await req('GET', '/api/assignments', null, t);
    if (aResp.status === 200 && aResp.body.length > 0) {
      const aId = aResp.body[0].id;
      const sr = await req('POST', `/api/assignments/${aId}/submit`, { content: 'Test submission from test-app.js', file_name: null }, t);
      result('Student', `Submit assignment #${aId}`, (sr.status === 200 && sr.body.success) ? 'PASS' : 'FAIL',
        `HTTP ${sr.status} — ${JSON.stringify(sr.body).slice(0,100)}`);
    } else {
      result('Student', 'Submit assignment', 'WARN', 'No assignments available to test');
    }
  } catch(e) {
    result('Student', 'Submit assignment', 'FAIL', e.message);
  }
}

async function testTeacherEndpoints() {
  const t = tokens.teacher;
  if (!t) { log('  ⛔ No teacher token — skip'); return; }
  log('\n── TEACHER ENDPOINTS ────────────────────────────────────────');

  const endpoints = [
    ['/api/teacher/stats',    'Teacher stats'],
    ['/api/teacher/courses',  'Teacher courses'],
    ['/api/teacher/students', 'Teacher students'],
    ['/api/assignments',      'Assignments list'],
  ];
  for (const [path, name] of endpoints) {
    try {
      const r = await req('GET', path, null, t);
      const ok = r.status === 200;
      result('Teacher', name, ok ? 'PASS' : 'FAIL',
        ok ? (Array.isArray(r.body) ? r.body.length + ' items' : JSON.stringify(r.body).slice(0,80)) : `HTTP ${r.status}`);
    } catch(e) {
      result('Teacher', name, 'FAIL', e.message);
    }
  }

  // View submissions for first assignment
  try {
    const aResp = await req('GET', '/api/assignments', null, t);
    if (aResp.status === 200 && aResp.body.length > 0) {
      const aId = aResp.body[0].id;
      const sr = await req('GET', `/api/assignments/${aId}/submissions`, null, t);
      result('Teacher', `Submissions for assignment #${aId}`, sr.status === 200 ? 'PASS' : 'FAIL',
        `${sr.status === 200 ? sr.body.length + ' submissions' : 'HTTP ' + sr.status}`);
    }
  } catch(e) {
    result('Teacher', 'View submissions', 'FAIL', e.message);
  }
}

async function testAdminEndpoints() {
  const t = tokens.admin;
  if (!t) { log('  ⛔ No admin token — skip'); return; }
  log('\n── ADMIN ENDPOINTS ──────────────────────────────────────────');

  const endpoints = [
    ['/api/admin/stats',  'Admin stats'],
    ['/api/admin/users',  'Users list'],
    ['/api/groups',       'Groups'],
    ['/api/courses',      'Courses'],
    ['/api/disciplines',  'Disciplines'],
  ];
  for (const [path, name] of endpoints) {
    try {
      const r = await req('GET', path, null, t);
      const ok = r.status === 200;
      result('Admin', name, ok ? 'PASS' : 'FAIL',
        ok ? (Array.isArray(r.body) ? r.body.length + ' items' : JSON.stringify(r.body).slice(0,80)) : `HTTP ${r.status}`);
    } catch(e) {
      result('Admin', name, 'FAIL', e.message);
    }
  }
}

async function testAttendance() {
  const t = tokens.teacher || tokens.admin;
  if (!t) return;
  log('\n── ATTENDANCE ───────────────────────────────────────────────');

  try {
    const r = await req('GET', '/api/attendance', null, t);
    result('Attendance', 'GET /api/attendance', r.status === 200 ? 'PASS' : 'FAIL', `HTTP ${r.status}`);
  } catch(e) {
    result('Attendance', 'GET /api/attendance', 'FAIL', e.message);
  }
}

async function testMessages() {
  const t = tokens.student;
  if (!t) return;
  log('\n── MESSAGES ─────────────────────────────────────────────────');

  try {
    const r = await req('GET', '/api/messages', null, t);
    result('Messages', 'GET /api/messages', r.status === 200 ? 'PASS' : 'FAIL', `HTTP ${r.status}`);
  } catch(e) {
    result('Messages', 'GET /api/messages', 'FAIL', e.message);
  }
}

async function testFrontendFiles() {
  log('\n── FRONTEND FILES ───────────────────────────────────────────');
  const pages = [
    'index.html', 'dashboard.html', 'teacher-dashboard.html',
    'admin-dashboard.html', 'courses.html', 'course-view.html',
    'grades.html', 'assignments.html', 'progress.html',
    'profile.html', 'schedule.html', 'materials.html',
    'config.js', 'api.js', 'styles.css',
  ];
  const dir = __dirname + '/frontend';
  for (const f of pages) {
    const exists = fs.existsSync(`${dir}/${f}`);
    result('Frontend', f, exists ? 'PASS' : 'FAIL', exists ? 'exists' : 'MISSING FILE');
  }

  // Check DEMO_MODE is false
  try {
    const cfg = fs.readFileSync(`${dir}/config.js`, 'utf8');
    const demoOff = cfg.includes('DEMO_MODE = false');
    result('Frontend', 'DEMO_MODE = false', demoOff ? 'PASS' : 'FAIL',
      demoOff ? 'real backend mode' : 'still in demo mode!');
  } catch(e) {
    result('Frontend', 'config.js readable', 'FAIL', e.message);
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  log('╔══════════════════════════════════════════════════════════╗');
  log('║       IT School LMS — Діагностичний тест                 ║');
  log(`║       ${new Date().toLocaleString('uk-UA')}                     ║`);
  log('╚══════════════════════════════════════════════════════════╝');
  log(`Base URL: ${BASE}\n`);

  await testFrontendFiles();
  const backendUp = await testHealth();
  if (backendUp) {
    await testAuth();
    await testStudentEndpoints();
    await testTeacherEndpoints();
    await testAdminEndpoints();
    await testAttendance();
    await testMessages();
  }

  // Summary
  const total = passed + failed + warned;
  log('\n╔══════════════════════════════════════════════════════════╗');
  log(`║  ПІДСУМОК: ${total} тестів                                    ║`);
  log(`║  ✅ PASS: ${passed}   ❌ FAIL: ${failed}   ⚠️  WARN: ${warned}              ║`);
  log('╚══════════════════════════════════════════════════════════╝');

  if (failed > 0) {
    log('\n❌ ПРОБЛЕМИ:');
    results.filter(r => r.status === 'FAIL').forEach(r => {
      log(`  • [${r.group}] ${r.name}: ${r.detail}`);
    });
  }

  // Save results
  fs.writeFileSync(LOG_FILE, logLines.join('\n'), 'utf8');
  fs.writeFileSync(JSON_FILE, JSON.stringify({ summary: { total, passed, failed, warned }, results }, null, 2), 'utf8');
  log(`\n📄 Логи збережені: ${LOG_FILE}`);
  log(`📊 JSON звіт:      ${JSON_FILE}`);
}

main().catch(e => {
  log('FATAL: ' + e.message);
  process.exit(1);
});
