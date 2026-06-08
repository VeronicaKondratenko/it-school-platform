// =====================================================================
//  IT School — Smart API Layer
//  Requires: config.js, mockData.js (loaded before this file)
// =====================================================================

// ─── Auth & Token helpers ────────────────────────────────────────────

function getToken()    { return localStorage.getItem('access_token'); }
function getRole()     { return localStorage.getItem('user_role'); }
function setAuth(token, role) {
    localStorage.setItem('access_token', token);
    localStorage.setItem('user_role', role);
}
function clearAuth() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('mock_role');
}

/** Redirect to login if not authenticated */
function requireAuth() {
    if (!getToken()) {
        window.location.href = 'index.html';
        return false;
    }
    return true;
}

/** Redirect to login and log out */
function logout() {
    clearAuth();
    window.location.href = '/index.html';
}

// ─── Simulated delay for realism in demo mode ────────────────────────
function mockDelay(ms = 120) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ─── LOGIN ───────────────────────────────────────────────────────────

/**
 * Login user.
 * DEMO_MODE: checks MOCK_CREDENTIALS, stores role, returns token-like string.
 * Real mode: POST /api/auth/login (OAuth2PasswordRequestForm).
 */
async function apiLogin(email, password) {
    if (DEMO_MODE) {
        await mockDelay(400);
        const cred = MOCK_CREDENTIALS[email];
        if (!cred || cred.password !== password) {
            throw new Error('Невірний email або пароль');
        }
        const fakeToken = `demo_token_${cred.role}_${Date.now()}`;
        setAuth(fakeToken, cred.role);
        localStorage.setItem('mock_role', cred.role);
        return { access_token: fakeToken, role: cred.role };
    }
    // Real mode
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    let resp;
    try {
        resp = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
    } catch (networkErr) {
        throw new Error(`Не вдалося підключитися до сервера (${API_BASE}). Перевірте, що backend запущений і доступний.`);
    }
    if (!resp.ok) {
        let detail = 'Невірний email або пароль';
        const contentType = resp.headers.get('content-type') || '';
        try {
            if (contentType.includes('application/json')) {
                const err = await resp.json();
                detail = err.detail || detail;
            } else {
                const text = (await resp.text()).trim();
                if (text) detail = text;
            }
        } catch (_parseErr) {
            // Keep fallback detail when response body cannot be parsed.
        }
        throw new Error(detail);
    }
    const data = await resp.json();
    setAuth(data.access_token, data.role);
    return data;
}

/**
 * Register user.
 * DEMO_MODE: throws error since data is static, but we can simulate it by storing in localStorage mock_role.
 * Real mode: POST /api/auth/register (JSON).
 */
async function apiRegister(fullName, email, password, role = 'student', extra = {}) {
    if (DEMO_MODE) {
        await mockDelay(400);
        const safeRole = role === 'teacher' ? 'student' : role;
        const fakeToken = `demo_token_new_${safeRole}_${Date.now()}`;
        setAuth(fakeToken, safeRole);
        localStorage.setItem('mock_role', safeRole);
        return { access_token: fakeToken, role: safeRole };
    }
    // Real mode
    const resp = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            full_name: fullName,
            email: email,
            password: password,
            role: role,
            patronymic: extra.patronymic || null,
            date_of_birth: extra.date_of_birth || null,
            phone: extra.phone || null
        })
    });
    if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Помилка реєстрації');
    }
    const data = await resp.json();
    setAuth(data.access_token, data.role);
    return data;
}

// ─── Generic GET ─────────────────────────────────────────────────────

/**
 * apiGet(endpoint)
 * DEMO_MODE: return MOCK_DATA[endpoint] with simulated delay.
 * Real mode: authenticated fetch to API_BASE + endpoint.
 */
// ─── XSS-safe HTML escaping (use before injecting user content via innerHTML) ─
function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ─── Unified API error parser ────────────────────────────────────────
// Surfaces the backend "detail" (string OR FastAPI validation array) so the UI
// can show a meaningful message instead of a generic "PUT error 400".
async function parseApiError(resp, fallback) {
    let detail;
    try {
        const err = await resp.json();
        if (Array.isArray(err.detail)) {
            detail = err.detail.map(e => (e && (e.msg || e.message)) || JSON.stringify(e)).join('; ');
        } else {
            detail = err.detail;
        }
    } catch (_) { /* non-JSON body */ }
    return new Error(detail || fallback || `HTTP ${resp.status}`);
}

async function apiGet(endpoint) {
    if (DEMO_MODE) {
        await mockDelay();

        // Dynamic details endpoint for course topics in teacher assignment modal
        const courseDetailsMatch = endpoint.match(/^\/api\/courses\/(\d+)$/);
        if (courseDetailsMatch) {
            const courseId = parseInt(courseDetailsMatch[1], 10);
            const course = (MOCK_DATA['/api/courses'] || []).find(c => c.id === courseId);
            return {
                id: courseId,
                title: course ? course.title : `Course ${courseId}`,
                topics: [
                    { id: courseId * 10 + 1, title: 'Основи теми' },
                    { id: courseId * 10 + 2, title: 'Практика та кейси' },
                ],
            };
        }

        const courseTopicsMatch = endpoint.match(/^\/api\/courses\/(\d+)\/topics$/);
        if (courseTopicsMatch) {
            const courseId = parseInt(courseTopicsMatch[1], 10);
            return (MOCK_DATA['/api/course_topics'] || []).filter(topic => topic.course_id === courseId);
        }

        const courseMaterialsMatch = endpoint.match(/^\/api\/courses\/(\d+)\/materials$/);
        if (courseMaterialsMatch) {
            const courseId = parseInt(courseMaterialsMatch[1], 10);
            return (MOCK_DATA['/api/course_materials'] || []).filter(m => m.course_id === courseId);
        }

        const topicDeleteMatch = endpoint.match(/^\/api\/courses\/topics\/(\d+)$/);
        if (topicDeleteMatch) {
            const topicId = parseInt(topicDeleteMatch[1], 10);
            const rows = MOCK_DATA['/api/course_topics'] || [];
            const idx = rows.findIndex(row => row.id === topicId);
            if (idx >= 0) rows.splice(idx, 1);
            return { ok: true };
        }

        const assignmentSubmissionsMatch = endpoint.match(/^\/api\/assignments\/(\d+)\/submissions$/);
        if (assignmentSubmissionsMatch) {
            const assignmentId = parseInt(assignmentSubmissionsMatch[1], 10);
            return (MOCK_DATA['/api/assignment_submissions'] || []).filter(s => s.assignment_id === assignmentId);
        }

        if (endpoint === '/api/messages/public') {
            return JSON.parse(JSON.stringify(MOCK_DATA['/api/messages/public'] || []));
        }

        if (endpoint === '/api/student/notifications') {
            return JSON.parse(JSON.stringify(MOCK_DATA['/api/student/notifications'] || []));
        }

        const disciplinesMatch = endpoint === '/api/disciplines';
        if (disciplinesMatch) {
            return JSON.parse(JSON.stringify(MOCK_DATA['/api/disciplines'] || []));
        }

        if (endpoint === '/api/assignments') {
            const role = localStorage.getItem('mock_role') || 'student';
            if (role === 'student') {
                const studentAssignments = JSON.parse(JSON.stringify(MOCK_DATA['/api/student/assignments'] || []));
                return studentAssignments.map(a => ({
                    ...a,
                    course_name: (MOCK_DATA['/api/courses'] || []).find(c => c.id === a.course_id)?.title || 'Курс',
                    submitted: a.status === 'submitted' || a.status === 'graded',
                    submission_content: a.submission_content || null,
                    submission_file_name: a.submission_file_name || null,
                    submission_locked: a.submission_locked || false,
                    grade_status: a.grade_status || (a.status === 'graded' ? 'graded' : null),
                    grade_score: a.grade_score || null,
                    grade_feedback: a.grade_feedback || null,
                }));
            }
            return JSON.parse(JSON.stringify(MOCK_DATA['/api/assignments'] || []));
        }

        if (endpoint === '/api/disciplines') {
            const predefined = MOCK_DATA['/api/disciplines'];
            if (Array.isArray(predefined)) {
                return JSON.parse(JSON.stringify(predefined));
            }

            const scheduleRows = MOCK_DATA['/api/schedule'] || [];
            const byId = new Map();
            scheduleRows.forEach(row => {
                const id = Number(row.discipline_id);
                if (!id || byId.has(id)) return;
                byId.set(id, {
                    id,
                    name: row.discipline_name || `Курс #${id}`,
                    course_id: null,
                    course_title: null,
                });
            });
            return Array.from(byId.values());
        }

        const data = MOCK_DATA[endpoint];
        if (data === undefined) {
            console.warn(`[DEMO] No mock data for: ${endpoint}`);
            return null;
        }
        return JSON.parse(JSON.stringify(data)); // deep clone
    }
    const token = getToken();
    console.log(`[API GET] ${endpoint} | Token: ${token ? 'EXISTS' : 'MISSING'}`);
    const resp = await fetch(`${API_BASE}${endpoint}`, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
    });
    console.log(`[API RESPONSE] ${endpoint} | Status: ${resp.status}`);
    if (resp.status === 401) { 
        console.warn('[AUTH] 401 Unauthorized, logging out');
        logout(); 
        return null; 
    }
    if (!resp.ok) {
        const errorMsg = `API error ${resp.status} for ${endpoint}`;
        console.error(`[API ERROR] ${errorMsg}`);
        throw new Error(errorMsg);
    }
    try {
        const data = await resp.json();
        console.log(`[API SUCCESS] ${endpoint} returned data`, data);
        return data;
    } catch (jsonErr) {
        console.error(`[API JSON ERROR] Failed to parse response for ${endpoint}:`, jsonErr);
        throw new Error(`Invalid JSON response from ${endpoint}`);
    }
}

// ─── Generic POST ────────────────────────────────────────────────────

/**
 * apiPost(endpoint, body, mockResponse?)
 * DEMO_MODE: simulate success, optionally push to mock array, return mockResponse.
 * Real mode: authenticated POST to API_BASE + endpoint.
 */
async function apiPost(endpoint, body, mockResponse = null) {
    if (DEMO_MODE) {
        await mockDelay(300);
        if (endpoint === '/api/admin/broadcast') {
            const targetRole = body?.target_role || null;
            const users = (MOCK_DATA['/api/admin/users'] || []).filter(u => !!u.telegram_id);
            const filtered = targetRole ? users.filter(u => u.role === targetRole) : users;
            return {
                message: 'Broadcast sent successfully',
                sent_count: filtered.length,
                total_users: filtered.length,
            };
        }

        if (endpoint === '/api/messages/public') {
            const newNotification = {
                id: Date.now(),
                title: body?.title || 'Сповіщення',
                message: body?.message || '',
                sender_name: 'Викладач',
                timestamp: new Date().toISOString(),
                target_role: body?.target_role || 'student',
            };
            const publicMessages = MOCK_DATA['/api/messages/public'] || (MOCK_DATA['/api/messages/public'] = []);
            publicMessages.unshift(newNotification);
            const studentNotifications = MOCK_DATA['/api/student/notifications'] || (MOCK_DATA['/api/student/notifications'] = []);
            studentNotifications.unshift(newNotification);
            return { success: true, telegram_sent: (MOCK_DATA['/api/admin/users'] || []).filter(u => u.role === (body?.target_role || 'student') && !!u.telegram_id).length };
        }

        const createTopicMatch = endpoint.match(/^\/api\/courses\/(\d+)\/topics$/);
        if (createTopicMatch) {
            const courseId = parseInt(createTopicMatch[1], 10);
            const topics = MOCK_DATA['/api/course_topics'] || (MOCK_DATA['/api/course_topics'] = []);
            const disciplines = MOCK_DATA['/api/disciplines'] || [];
            const discipline = disciplines.find(item => item.id === body?.discipline_id && item.course_id === courseId);
            const newTopic = {
                id: Date.now(),
                title: body?.title || 'Нова тема',
                discipline_id: body?.discipline_id || discipline?.id || null,
                discipline_name: discipline?.course_title || discipline?.name || 'Курс',
                course_id: courseId,
            };
            topics.unshift(newTopic);
            return newTopic;
        }

        const createMaterialMatch = endpoint.match(/^\/api\/courses\/(\d+)\/materials$/);
        if (createMaterialMatch) {
            const courseId = parseInt(createMaterialMatch[1], 10);
            const materials = MOCK_DATA['/api/course_materials'] || (MOCK_DATA['/api/course_materials'] = []);
            const newMaterial = {
                id: Date.now(),
                course_id: courseId,
                title: body?.title || 'Матеріал',
                body: body?.body || '',
            };
            materials.unshift(newMaterial);
            return newMaterial;
        }

        // Dynamic student assignment submission endpoint (legacy)
        const submitMatch = endpoint.match(/^\/api\/student\/assignments\/(\d+)\/submit$/);
        if (submitMatch) {
            const assignmentId = parseInt(submitMatch[1], 10);
            const assignments = MOCK_DATA['/api/student/assignments'] || [];
            const target = assignments.find(a => a.id === assignmentId);
            if (target) {
                target.status = 'submitted';
                target.submission_locked = true;
            }
            return mockResponse || { ok: true, assignment_id: assignmentId, status: 'submitted' };
        }

        // Current assignment submission endpoint used by assignments.html
        const assignmentSubmitMatch = endpoint.match(/^\/api\/assignments\/(\d+)\/submit$/);
        if (assignmentSubmitMatch) {
            const assignmentId = parseInt(assignmentSubmitMatch[1], 10);
            const assignments = MOCK_DATA['/api/student/assignments'] || [];
            const target = assignments.find(a => a.id === assignmentId);
            if (target) {
                if (target.submission_locked) {
                    throw new Error('Submission is locked. Ask teacher to reset before resubmitting');
                }
                target.status = 'submitted';
                target.submission_content = body?.content || null;
                target.submission_file_name = body?.file_name || null;
                target.submission_locked = true;
            }
            return {
                success: true,
                assignment_id: assignmentId,
                status: 'submitted',
                file_name: body?.file_name || null,
                locked: true,
            };
        }

        const gradeMatch = endpoint.match(/^\/api\/assignments\/submissions\/(\d+)\/grade$/);
        if (gradeMatch) {
            const submissionId = parseInt(gradeMatch[1], 10);
            const submissions = MOCK_DATA['/api/assignment_submissions'] || [];
            const submission = submissions.find(s => s.submission_id === submissionId);
            if (submission) {
                submission.grade_status = body?.status || (body?.score !== null && body?.score !== undefined ? 'graded' : 'reviewed');
                submission.grade_score = body?.score ?? null;
                submission.grade_feedback = body?.feedback ?? null;
                submission.is_locked = true;

                const studentAssignments = MOCK_DATA['/api/student/assignments'] || [];
                const assignment = studentAssignments.find(a => a.id === submission.assignment_id);
                if (assignment) {
                    assignment.grade_status = submission.grade_status;
                    assignment.grade_score = submission.grade_score;
                    assignment.grade_feedback = submission.grade_feedback;
                    assignment.submission_locked = true;
                    assignment.status = submission.grade_status === 'graded' ? 'graded' : 'submitted';
                }
            }
            return { success: true, submission_id: submissionId };
        }

        const resetMatch = endpoint.match(/^\/api\/assignments\/submissions\/(\d+)\/reset$/);
        if (resetMatch) {
            const submissionId = parseInt(resetMatch[1], 10);
            const submissions = MOCK_DATA['/api/assignment_submissions'] || [];
            const submission = submissions.find(s => s.submission_id === submissionId);
            if (submission) {
                submission.is_locked = false;
                const studentAssignments = MOCK_DATA['/api/student/assignments'] || [];
                const assignment = studentAssignments.find(a => a.id === submission.assignment_id);
                if (assignment) assignment.submission_locked = false;
            }
            return { success: true, submission_id: submissionId, locked: false };
        }

        const enrollMatch = endpoint.match(/^\/api\/groups\/(\d+)\/enroll\/(\d+)$/);
        if (enrollMatch) {
            return { message: 'Student enrolled to group (demo)' };
        }

        // Auto-push to mock arrays if they exist
        if (MOCK_DATA[endpoint] && Array.isArray(MOCK_DATA[endpoint])) {
            const newItem = { id: Date.now(), ...body };
            MOCK_DATA[endpoint].push(newItem);
            return mockResponse || newItem;
        }
        return mockResponse || { ok: true, ...body };
    }
    const token = getToken();
    const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify(body)
    });
    if (resp.status === 401) { logout(); return null; }
    if (!resp.ok) throw await parseApiError(resp, `POST error ${resp.status}`);
    return resp.json();
}

// ─── Generic PUT ─────────────────────────────────────────────────────

async function apiPut(endpoint, body) {
    if (DEMO_MODE) {
        await mockDelay(200);
        const courseUpdateMatch = endpoint.match(/^\/api\/courses\/(\d+)$/);
        if (courseUpdateMatch) {
            const courseId = parseInt(courseUpdateMatch[1], 10);
            const rows = MOCK_DATA['/api/courses'] || [];
            const idx = rows.findIndex(r => r.id === courseId);
            if (idx >= 0) rows[idx] = { ...rows[idx], ...body };
            return idx >= 0 ? rows[idx] : { id: courseId, ...body };
        }

        const topicUpdateMatch = endpoint.match(/^\/api\/courses\/topics\/(\d+)$/);
        if (topicUpdateMatch) {
            const topicId = parseInt(topicUpdateMatch[1], 10);
            const rows = MOCK_DATA['/api/course_topics'] || [];
            const idx = rows.findIndex(r => r.id === topicId);
            if (idx >= 0) rows[idx] = { ...rows[idx], ...body };
            return idx >= 0 ? rows[idx] : { id: topicId, ...body };
        }

        const scheduleUpdateMatch = endpoint.match(/^\/api\/schedule\/(\d+)$/);
        if (scheduleUpdateMatch) {
            const scheduleId = parseInt(scheduleUpdateMatch[1], 10);
            const rows = MOCK_DATA['/api/schedule'] || [];
            const idx = rows.findIndex(r => r.id === scheduleId);
            if (idx >= 0) rows[idx] = { ...rows[idx], ...body };
            return idx >= 0 ? rows[idx] : { id: scheduleId, ...body };
        }

        const adminUserUpdateMatch = endpoint.match(/^\/api\/admin\/users\/(\d+)$/);
        if (adminUserUpdateMatch) {
            const userId = parseInt(adminUserUpdateMatch[1], 10);
            const users = MOCK_DATA['/api/admin/users'] || [];
            const user = users.find(u => u.id === userId);
            if (user) Object.assign(user, body);
            return { ok: true, ...(user || {}), ...body };
        }
        return { ok: true, ...body };
    }
    const token = getToken();
    let resp;
    try {
        resp = await fetch(`${API_BASE}${endpoint}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: JSON.stringify(body || {})
        });
    } catch (networkErr) {
        console.error('PUT network error:', endpoint, networkErr);
        throw new Error(`Не вдалося підключитися до backend під час збереження (${endpoint}). Перевірте Render Logs або повторіть після оновлення backend.`);
    }
    if (resp.status === 401) { logout(); return null; }
    if (!resp.ok) throw await parseApiError(resp, `PUT error ${resp.status}`);
    return resp.json();
}


async function apiPatch(endpoint, body = {}) {
    if (DEMO_MODE) {
        await mockDelay(200);
        return { ok: true, ...body };
    }
    const token = getToken();
    const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify(body || {})
    });
    if (resp.status === 401) { logout(); return null; }
    if (!resp.ok) throw await parseApiError(resp, `PATCH error ${resp.status}`);
    return resp.json();
}

// ─── Generic DELETE ──────────────────────────────────────────────────

async function apiDelete(endpoint) {
    if (DEMO_MODE) {
        await mockDelay(200);
        const materialDeleteMatch = endpoint.match(/^\/api\/courses\/(\d+)\/materials\/(\d+)$/);
        if (materialDeleteMatch) {
            const materialId = parseInt(materialDeleteMatch[2], 10);
            const materials = MOCK_DATA['/api/course_materials'] || [];
            const idx = materials.findIndex(m => m.id === materialId);
            if (idx >= 0) materials.splice(idx, 1);
            return { message: 'Material deleted' };
        }
        const assignmentDeleteMatch = endpoint.match(/^\/api\/assignments\/(\d+)$/);
        if (assignmentDeleteMatch) {
            const assignmentId = parseInt(assignmentDeleteMatch[1], 10);

            const assignments = MOCK_DATA['/api/assignments'] || [];
            const assignmentIndex = assignments.findIndex(a => a.id === assignmentId);
            if (assignmentIndex >= 0) assignments.splice(assignmentIndex, 1);

            const studentAssignments = MOCK_DATA['/api/student/assignments'] || [];
            for (let i = studentAssignments.length - 1; i >= 0; i -= 1) {
                if (studentAssignments[i].id === assignmentId) {
                    studentAssignments.splice(i, 1);
                }
            }

            const submissions = MOCK_DATA['/api/assignment_submissions'] || [];
            for (let i = submissions.length - 1; i >= 0; i -= 1) {
                if (submissions[i].assignment_id === assignmentId) {
                    submissions.splice(i, 1);
                }
            }

            return { success: true, assignment_id: assignmentId };
        }

        const courseDeleteMatch = endpoint.match(/^\/api\/courses\/(\d+)$/);
        if (courseDeleteMatch) {
            const courseId = parseInt(courseDeleteMatch[1], 10);
            const rows = MOCK_DATA['/api/courses'] || [];
            const idx = rows.findIndex(r => r.id === courseId);
            if (idx >= 0) rows.splice(idx, 1);
            return { ok: true };
        }

        const topicDeleteMatch = endpoint.match(/^\/api\/courses\/topics\/(\d+)$/);
        if (topicDeleteMatch) {
            const topicId = parseInt(topicDeleteMatch[1], 10);
            const rows = MOCK_DATA['/api/course_topics'] || [];
            const idx = rows.findIndex(r => r.id === topicId);
            if (idx >= 0) rows.splice(idx, 1);
            return { ok: true };
        }

        const userDeleteMatch = endpoint.match(/^\/api\/admin\/users\/(\d+)$/);
        if (userDeleteMatch) {
            const userId = parseInt(userDeleteMatch[1], 10);
            const rows = MOCK_DATA['/api/admin/users'] || [];
            const idx = rows.findIndex(r => r.id === userId);
            if (idx >= 0) rows.splice(idx, 1);
            return { ok: true };
        }

        return { ok: true };
    }
    const token = getToken();
    const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (resp.status === 401) { logout(); return null; }
    if (!resp.ok) throw await parseApiError(resp, `DELETE error ${resp.status}`);
    return resp.json();
}

// ─── Convenience helpers ─────────────────────────────────────────────

/** Get current user (respects mock role) */
async function fetchCurrentUser() {
    if (DEMO_MODE) {
        await mockDelay();
        const role = localStorage.getItem('mock_role') || 'student';
        return JSON.parse(JSON.stringify(MOCK_DATA[role]));
    }
    return apiGet('/api/users/me');
}

/** Update own profile */
async function updateProfile(data) {
    if (DEMO_MODE) {
        await mockDelay(200);
        const role = localStorage.getItem('mock_role') || 'student';
        Object.assign(MOCK_DATA[role], data);
        return MOCK_DATA[role];
    }
    return apiPut('/api/users/me', data);
}

/** Fetch report data as JSON for table rendering */
async function fetchReportData(type) {
    if (DEMO_MODE) {
        await mockDelay(300);
        const reportMap = {
            attendance: {
                title: 'Attendance Report',
                columns: ['metric', 'value'],
                rows: [
                    { metric: 'Present', value: 24 },
                    { metric: 'Late', value: 4 },
                    { metric: 'Absent', value: 3 },
                    { metric: 'Attendance Rate %', value: 77.4 },
                ],
            },
            task_completion: {
                title: 'Task Completion Report',
                columns: ['metric', 'value'],
                rows: [
                    { metric: 'Assignments', value: 12 },
                    { metric: 'Submissions', value: 9 },
                    { metric: 'Completion Rate %', value: 75.0 },
                ],
            },
            teacher_subject_mapping: {
                title: 'Teacher-Subject Mapping',
                columns: ['teacher', 'group', 'course'],
                rows: [
                    { teacher: 'Ivan Ivanov', group: 'WEB-2024-A', course: 'Веб-розробка' },
                    { teacher: 'Anna Shevchenko', group: 'DB-2024-B', course: 'Бази даних' },
                ],
            },
            course_statistics: {
                title: 'Course Statistics',
                columns: ['course', 'disciplines', 'topics', 'assignments'],
                rows: [
                    { course: 'Веб-розробка', disciplines: 2, topics: 6, assignments: 4 },
                    { course: 'Бази даних', disciplines: 2, topics: 5, assignments: 3 },
                ],
            },
            active_students: {
                title: 'Active Students',
                columns: ['student', 'email', 'submissions'],
                rows: [
                    { student: 'Іван Петренко', email: 'student@example.com', submissions: 4 },
                    { student: 'Марія Сидоренко', email: 'maria@example.com', submissions: 3 },
                ],
            },
            graduated_students: {
                title: 'Graduated Students',
                columns: ['student', 'email', 'avg_score', 'status'],
                rows: [
                    { student: 'Іван Петренко', email: 'student@example.com', avg_score: 87.5, status: 'Graduated' },
                ],
            },
            excellent_students: {
                title: 'Excellent Students',
                columns: ['student', 'email', 'avg_score', 'badge'],
                rows: [
                    { student: 'Олена Тимченко', email: 'olena@example.com', avg_score: 93.0, badge: 'Excellent' },
                ],
            },
        };

        const mapped = reportMap[type] || { title: 'Demo Report', columns: ['metric', 'value'], rows: [{ metric: 'No data', value: 0 }] };
        return {
            type,
            title: mapped.title,
            columns: mapped.columns,
            rows: mapped.rows,
            summary: { mode: 'demo' },
            generated_at: new Date().toISOString(),
        };
    }
    const token = getToken();
    const resp = await fetch(`${API_BASE}/api/reports?type=${encodeURIComponent(type)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!resp.ok) throw await parseApiError(resp, 'Помилка генерації звіту');
    return resp.json();
}

/** Backward-compatible report trigger */
async function exportReport(type) {
    return fetchReportData(type);
}

/** Send AI chat message */
async function askAI(message, courseId = null) {
    if (DEMO_MODE) {
        await mockDelay(600);
        const msg = message.toLowerCase();
        let category = 'general';
        let response = 'Привіт! Я AI-асистент IT School. Чим можу допомогти?';
        if (msg.includes('оплат') || msg.includes('реєстр') || msg.includes('розклад') || msg.includes('група') || msg.includes('кабінет')) {
            category = 'administrative';
            response = 'Це адміністративне питання. Я передав його викладачу — ви отримаєте відповідь найближчим часом. Також можете знайти інформацію в розділі «Розклад» або звернутися до адміністратора.';
            // Simulate escalation
            MOCK_DATA['/api/messages/inbox'].unshift({
                id: Date.now(), sender_name: 'Ви (студент)', sender_email: 'student@example.com',
                content: message, timestamp: new Date().toISOString(),
                status: 'pending', is_escalated: true, telegram_id: null
            });
        } else if (msg.includes('код') || msg.includes('python') || msg.includes('js') || msg.includes('алгоритм') || msg.includes('sql') || msg.includes('css') || msg.includes('html')) {
            category = 'academic';
            response = 'Чудове питання! Порада: розбийте задачу на менші кроки та спробуйте спочатку написати псевдокод. Якщо потрібна додаткова допомога — зверніться до викладача або ознайомтесь з матеріалами курсу.';
        }
        return { category, response };
    }
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const resp = await fetch(`${API_BASE}/api/chat/ask`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message, course_id: courseId })
    });
    if (!resp.ok) {
        throw await parseApiError(resp, 'Помилка AI-асистента');
    }
    return resp.json();
}

// ─── Reply to student message (teacher inbox) ────────────────────────

async function replyToMessage(messageId, replyText) {
    if (DEMO_MODE) {
        await mockDelay(400);
        const msg = MOCK_DATA['/api/messages/inbox'].find(m => m.id === messageId);
        if (msg) {
            msg.status = 'answered';
            msg.reply = replyText;
        }
        return { ok: true };
    }
    return apiPost(`/api/messages/reply/${messageId}`, { reply: replyText });
}

// ─── Toast notification helper ───────────────────────────────────────

function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
        document.body.appendChild(container);
    }
    const colors = { success:'#10b981', error:'#ef4444', warning:'#f59e0b', info:'#3b82f6' };
    const accent = colors[type] || colors.info;
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    if (!document.getElementById('_toastKF')) {
        const s = document.createElement('style');
        s.id = '_toastKF';
        s.textContent = '@keyframes _toastIn{from{opacity:0;transform:translateX(12px)}to{opacity:1;transform:translateX(0)}}';
        document.head.appendChild(s);
    }
    const toast = document.createElement('div');
    toast.style.cssText = [
        `background:${isDark ? '#1e2540' : '#ffffff'}`,
        `color:${isDark ? '#e2e8f0' : '#0f172a'}`,
        `border:1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.1)'}`,
        `border-left:3px solid ${accent}`,
        'border-radius:10px','padding:.7rem 1rem',
        `box-shadow:0 8px 24px rgba(0,0,0,${isDark ? '.35' : '.1'})`,
        'font-family:Manrope,sans-serif','font-size:.875rem','font-weight:600',
        'max-width:300px','pointer-events:auto','animation:_toastIn .2s ease'
    ].join(';');
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

// ─── Demo mode banner ────────────────────────────────────────────────

function showDemoBanner() {
    if (!DEMO_MODE) return;
    if (document.getElementById('_demoBanner')) return;
    const banner = document.createElement('div');
    banner.id = '_demoBanner';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:linear-gradient(90deg,#d97706,#b45309);color:#fff;text-align:center;padding:5px 1rem;font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:center;gap:6px;';
    banner.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> ДЕМО-РЕЖИМ — тестові дані. Для реального бекенду: <code style="background:rgba(0,0,0,0.25);padding:0 4px;border-radius:3px;">DEMO_MODE = false</code>';
    document.body.prepend(banner);
    document.body.style.paddingTop = (parseFloat(document.body.style.paddingTop) || 0) + 30 + 'px';
}

// ─── Floating Chat Widget (Students only) ────────────────────────────

function initStudentChatWidget() {
    const role = getRole();
    if (role !== 'student') return;
    
    // Check if already injected
    if (document.getElementById('ai-chat-widget')) return;

    // Strong local styles for the AI widget.
    // They intentionally use a widget id + !important because global theme files
    // contain generic input/select rules with !important and can otherwise make
    // the text white on the white AI input.
    if (!document.getElementById('ai-chat-widget-safe-styles')) {
        const chatStyle = document.createElement('style');
        chatStyle.id = 'ai-chat-widget-safe-styles';
        chatStyle.textContent = `
            #ai-chat-widget, #ai-chat-widget * { box-sizing: border-box; }
            #ai-chat-window { background: #ffffff !important; color: #0f172a !important; }
            #ai-chat-messages { background: #f8fafc !important; color: #0f172a !important; }
            #ai-chat-form { background: #ffffff !important; color: #0f172a !important; }
            #ai-chat-input, #ai-chat-course {
                background: #ffffff !important;
                color: #0f172a !important;
                -webkit-text-fill-color: #0f172a !important;
                caret-color: #2563eb !important;
                border-color: #cbd5e1 !important;
                opacity: 1 !important;
            }
            #ai-chat-input::placeholder {
                color: #64748b !important;
                -webkit-text-fill-color: #64748b !important;
                opacity: 1 !important;
            }
            #ai-chat-input:focus, #ai-chat-course:focus {
                background: #ffffff !important;
                color: #0f172a !important;
                -webkit-text-fill-color: #0f172a !important;
                border-color: #2563eb !important;
                box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16) !important;
            }
            #ai-chat-input:disabled {
                background: #f8fafc !important;
                color: #0f172a !important;
                -webkit-text-fill-color: #0f172a !important;
                opacity: .72 !important;
            }
            #ai-chat-course option {
                background: #ffffff !important;
                color: #0f172a !important;
            }
        `;
        document.head.appendChild(chatStyle);
    }

    const widgetHTML = `
        <div id="ai-chat-widget" style="position:fixed;bottom:24px;right:24px;z-index:9999;font-family:Inter,sans-serif;">
            <!-- Chat Window -->
            <div id="ai-chat-window" style="display:none;width:320px;height:450px;background:#fff;color:#0f172a;border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.15);flex-direction:column;overflow:hidden;margin-bottom:16px;border:1px solid #e2e8f0;transition:all 0.3s ease;">
                <!-- Header -->
                <div style="background:linear-gradient(135deg,#2563eb,#1d4ed8);color:white;padding:16px;display:flex;justify-content:space-between;align-items:center;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:20px;"></span>
                        <h3 style="margin:0;font-size:16px;font-weight:600;">IT School AI</h3>
                    </div>
                    <button id="ai-chat-close" style="background:none;border:none;color:white;cursor:pointer;font-size:20px;padding:0;line-height:1;">&times;</button>
                </div>
                <div style="padding:10px 12px;border-bottom:1px solid #e2e8f0;background:#f8fafc;">
                    <label for="ai-chat-course" style="display:block;font-size:12px;color:#475569;margin-bottom:6px;font-weight:600;">Контекст курсу</label>
                    <select id="ai-chat-course" style="width:100%;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;color:#0f172a!important;-webkit-text-fill-color:#0f172a!important;background:white!important;">
                        <option value="">Без курсу (загальне питання)</option>
                    </select>
                    <div id="ai-chat-course-note" style="font-size:11px;color:#64748b;margin-top:6px;">Курс обирати не обовʼязково. Оберіть його, щоб AI враховував навчальний контекст і правильно переадресовував складні запити викладачу.</div>
                </div>
                <!-- Messages Area -->
                <div id="ai-chat-messages" style="flex:1;padding:16px;overflow-y:auto;background:#f8fafc;display:flex;flex-direction:column;gap:12px;font-size:14px;">
                    <div style="align-self:flex-start;background:#e2e8f0;color:#1e293b;padding:10px 14px;border-radius:12px;border-bottom-left-radius:2px;max-width:85%;">
                        Привіт! Я ваш AI-асистент. Запитайте мене про навчання — за потреби оберіть курс зверху, щоб я врахував його контекст.
                    </div>
                </div>
                <!-- Input Area -->
                <form id="ai-chat-form" style="display:flex;padding:12px;border-top:1px solid #e2e8f0;background:#fff;color:#0f172a;gap:8px;">
                    <input type="text" id="ai-chat-input" placeholder="Напишіть повідомлення..." required style="flex:1;padding:10px 14px;border:1px solid #cbd5e1;border-radius:20px;outline:none;font-family:inherit;font-size:14px;color:#0f172a!important;-webkit-text-fill-color:#0f172a!important;background:#fff!important;caret-color:#2563eb!important;">
                    <button type="submit" id="ai-chat-send" style="background:#2563eb;color:#fff;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background 0.2s;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </form>
            </div>
            
            <!-- Floating Button -->
            <button id="ai-chat-toggle" style="width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:white;border:none;box-shadow:0 6px 16px rgba(37,99,235,0.4);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform 0.2s;margin-left:auto;display:block;">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
            </button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', widgetHTML);
    
    const widget = document.getElementById('ai-chat-widget');
    const windowEl = document.getElementById('ai-chat-window');
    const toggleBtn = document.getElementById('ai-chat-toggle');
    const closeBtn = document.getElementById('ai-chat-close');
    const form = document.getElementById('ai-chat-form');
    const input = document.getElementById('ai-chat-input');
    const sendBtn = document.getElementById('ai-chat-send');

    // Extra runtime guard for browsers/themes that override input text color.
    input.style.setProperty('color', '#0f172a', 'important');
    input.style.setProperty('-webkit-text-fill-color', '#0f172a', 'important');
    input.style.setProperty('background', '#ffffff', 'important');
    input.style.setProperty('caret-color', '#2563eb', 'important');
    input.style.setProperty('opacity', '1', 'important');

    const messagesEl = document.getElementById('ai-chat-messages');
    const courseSelect = document.getElementById('ai-chat-course');
    const courseNote = document.getElementById('ai-chat-course-note');
    let selectedCourseId = null;

    function setInputEnabled(enabled) {
        input.disabled = !enabled;
        sendBtn.disabled = !enabled;
        sendBtn.style.opacity = enabled ? '1' : '0.6';
        sendBtn.style.cursor = enabled ? 'pointer' : 'not-allowed';
        input.placeholder = 'Напишіть повідомлення...';
    }

    async function loadStudentCoursesForChat() {
        courseSelect.innerHTML = '<option value="">Без курсу (загальне питання)</option>';
        try {
            const studentCourses = await apiGet('/api/student/courses') || [];
            studentCourses.forEach(course => {
                const option = document.createElement('option');
                option.value = String(course.course_id);
                option.textContent = course.course_title || `Курс #${course.course_id}`;
                courseSelect.appendChild(option);
            });
            setInputEnabled(true);
        } catch (error) {
            // Even if courses fail to load, general questions are still allowed.
            courseNote.textContent = 'Не вдалося завантажити список курсів, але ви можете поставити загальне питання.';
            setInputEnabled(true);
        }
    }

    courseSelect.addEventListener('change', () => {
        selectedCourseId = courseSelect.value ? Number(courseSelect.value) : null;
        const selectedTitle = courseSelect.options[courseSelect.selectedIndex]?.text || '';
        if (selectedCourseId) {
            courseNote.textContent = `Поточний контекст: ${selectedTitle}.`;
        } else {
            courseNote.textContent = 'Курс обирати не обовʼязково. Оберіть його, щоб AI враховував навчальний контекст.';
        }
        input.focus();
    });
    
    // Initial state: hidden
    windowEl.style.display = 'none';
    
    function toggleChat() {
        if (windowEl.style.display === 'none') {
            windowEl.style.display = 'flex';
            toggleBtn.style.transform = 'scale(0.8)';
            if (!input.disabled) input.focus();
        } else {
            windowEl.style.display = 'none';
            toggleBtn.style.transform = 'scale(1)';
        }
    }
    
    toggleBtn.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', toggleChat);
    
    function appendMessage(text, isUser = false) {
        const msg = document.createElement('div');
        msg.style.padding = '10px 14px';
        msg.style.borderRadius = '12px';
        msg.style.maxWidth = '85%';
        msg.style.wordBreak = 'break-word';
        
        if (isUser) {
            msg.style.alignSelf = 'flex-end';
            msg.style.background = '#2563eb';
            msg.style.color = '#fff';
            msg.style.borderBottomRightRadius = '2px';
        } else {
            msg.style.alignSelf = 'flex-start';
            msg.style.background = '#e2e8f0';
            msg.style.color = '#1e293b';
            msg.style.borderBottomLeftRadius = '2px';
        }
        
        msg.textContent = text;
        messagesEl.appendChild(msg);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        
        appendMessage(text, true);
        input.value = '';
        input.disabled = true;
        
        // Add loading indicator
        const loadingId = 'ai-chat-loading-' + Date.now();
        const loadingDiv = document.createElement('div');
        loadingDiv.id = loadingId;
        loadingDiv.style.alignSelf = 'flex-start';
        loadingDiv.style.color = '#64748b';
        loadingDiv.style.fontSize = '12px';
        loadingDiv.textContent = 'AI друкує...';
        messagesEl.appendChild(loadingDiv);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        
        try {
            const result = await askAI(text, selectedCourseId);
            document.getElementById(loadingId).remove();
            appendMessage(result.response || 'Неможливо отримати відповідь', false);
        } catch (error) {
            document.getElementById(loadingId).remove();
            appendMessage(error.message || 'Помилка з\'єднання з AI. Спробуйте пізніше.', false);
        } finally {
            input.disabled = false;
            input.focus();
        }
    });

    setInputEnabled(true);
    loadStudentCoursesForChat();
}

// ─── Role-aware sidebar stability ─────────────────────────────────
// Shared pages used to keep their own sidebar markup, so admin/teacher could see
// a student menu or lose the account block. This block rebuilds staff sidebars in
// one consistent way, keeps active menu items highlighted, and adds the account
// avatar/name/role everywhere for the current role.
function roleNavIcon(name) {
    const icons = {
        overview: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
        users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        course: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
        group: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>',
        calendar: '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
        report: '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>',
        bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
        chat: '<path d="M21 15a4 4 0 0 1-4 4H7l-4 4V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/>',
        grade: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
        task: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
        profile: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    };
    return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icons[name] || icons.overview}</svg>`;
}

function roleLabel(role) {
    return role === 'admin' ? 'Адмін' : role === 'teacher' ? 'Викладач' : 'Студент';
}

function initialsFromName(name, email) {
    const raw = String(name || '').trim();
    if (raw) {
        const parts = raw.split(/\s+/).filter(Boolean);
        if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
        return raw.slice(0, 2).toUpperCase();
    }
    return String(email || 'IT').slice(0, 2).toUpperCase();
}

function currentRolePage() {
    return (location.pathname.split('/').pop() || 'index.html').toLowerCase();
}

function isNativeDashboardPage() {
    const page = currentRolePage();
    return page === 'admin-dashboard.html' || page === 'teacher-dashboard.html';
}

function adminNavItems() {
    return [
        { type: 'label', text: 'Панель адміністратора' },
        { href: 'admin-dashboard.html#overview', label: 'Огляд', icon: 'overview', active: () => currentRolePage() === 'admin-dashboard.html' && (!location.hash || location.hash === '#overview') },
        { type: 'label', text: 'Управління' },
        { href: 'admin-dashboard.html#users', label: 'Користувачі', icon: 'users', active: () => currentRolePage() === 'admin-dashboard.html' && location.hash === '#users' },
        { href: 'admin-dashboard.html#courses', label: 'Курси', icon: 'course', active: () => currentRolePage() === 'admin-dashboard.html' && location.hash === '#courses' },
        { href: 'admin-dashboard.html#groups', label: 'Групи', icon: 'group', active: () => currentRolePage() === 'admin-dashboard.html' && location.hash === '#groups' },
        // Calendar is a real shared page for admins, not only a short table inside the dashboard.
        // Keeping it as schedule.html makes the active state and visual shell consistent when the
        // admin opens the full calendar from the sidebar.
        { href: 'schedule.html', label: 'Розклад', icon: 'calendar', active: () => currentRolePage() === 'schedule.html' || (currentRolePage() === 'admin-dashboard.html' && location.hash === '#schedule') },
        { type: 'label', text: 'Комунікація' },
        { href: 'admin-questions.html', label: 'Звернення', icon: 'chat', active: () => currentRolePage() === 'admin-questions.html' },
        { href: 'admin-dashboard.html#notifications', label: 'Сповіщення', icon: 'bell', active: () => currentRolePage() === 'admin-dashboard.html' && location.hash === '#notifications' },
        { type: 'label', text: 'Аналітика' },
        { href: 'admin-dashboard.html#reports', label: 'Звіти', icon: 'report', active: () => currentRolePage() === 'admin-dashboard.html' && location.hash === '#reports' },
        { type: 'label', text: 'Профіль' },
        { href: 'profile.html', label: 'Профіль', icon: 'profile', active: () => currentRolePage() === 'profile.html' },
    ];
}

function teacherNavItems() {
    return [
        { type: 'label', text: 'Панель викладача' },
        { href: 'teacher-dashboard.html#overview', label: 'Огляд', icon: 'overview', active: () => currentRolePage() === 'teacher-dashboard.html' && (!location.hash || location.hash === '#overview') },
        { type: 'label', text: 'Навчання' },
        { href: 'teacher-dashboard.html#courses', label: 'Мої курси', icon: 'course', active: () => currentRolePage() === 'teacher-dashboard.html' && location.hash === '#courses' },
        { href: 'teacher-dashboard.html#students', label: 'Студенти', icon: 'users', active: () => currentRolePage() === 'teacher-dashboard.html' && location.hash === '#students' },
        { href: 'teacher-dashboard.html#assignments', label: 'Завдання', icon: 'task', active: () => currentRolePage() === 'teacher-dashboard.html' && location.hash === '#assignments' },
        { href: 'teacher-dashboard.html#grades', label: 'Оцінки', icon: 'grade', active: () => currentRolePage() === 'teacher-dashboard.html' && location.hash === '#grades' },
        { href: 'teacher-dashboard.html#attendance', label: 'Відвідуваність', icon: 'calendar', active: () => currentRolePage() === 'teacher-dashboard.html' && location.hash === '#attendance' },
        { type: 'label', text: 'Комунікація' },
        { href: 'teacher-questions.html', label: 'Звернення студентів', icon: 'chat', active: () => currentRolePage() === 'teacher-questions.html' },
        { type: 'label', text: 'Профіль' },
        { href: 'profile.html', label: 'Профіль', icon: 'profile', active: () => currentRolePage() === 'profile.html' },
    ];
}

function roleNavItemsFor(role) {
    if (role === 'admin') return adminNavItems();
    if (role === 'teacher') return teacherNavItems();
    return null;
}

function injectRoleSidebarStyles() {
    if (document.getElementById('role-sidebar-consistency-style')) return;
    const s = document.createElement('style');
    s.id = 'role-sidebar-consistency-style';
    s.textContent = `
        body.role-admin .sidebar, body.role-teacher .sidebar, body.role-student .sidebar{
            background:#1a2744!important;color:#fff!important;border-right:1px solid rgba(255,255,255,.08)!important;
        }
        body.role-admin .sidebar-logo, body.role-teacher .sidebar-logo, body.role-student .sidebar-logo,
        body.role-admin .sidebar-profile, body.role-teacher .sidebar-profile, body.role-student .sidebar-profile,
        body.role-admin .sidebar-bottom, body.role-teacher .sidebar-bottom, body.role-student .sidebar-bottom{
            border-color:rgba(255,255,255,.08)!important;
        }
        body.role-admin .sidebar-logo span, body.role-teacher .sidebar-logo span, body.role-student .sidebar-logo span,
        body.role-admin .sidebar-pname, body.role-teacher .sidebar-pname, body.role-student .sidebar-pname{
            color:#fff!important;-webkit-text-fill-color:#fff!important;
        }
        body.role-admin .sidebar-profile, body.role-teacher .sidebar-profile, body.role-student .sidebar-profile{
            padding:1.25rem 1rem!important;text-align:center!important;border-bottom:1px solid rgba(255,255,255,.08)!important;
        }
        body.role-admin .sidebar-avatar, body.role-teacher .sidebar-avatar, body.role-student .sidebar-avatar{
            width:64px!important;height:64px!important;border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
            font-family:'Unbounded',sans-serif!important;font-size:1.45rem!important;font-weight:900!important;color:#fff!important;margin:0 auto .75rem!important;
            box-shadow:0 0 20px rgba(37,99,235,.22)!important;
        }
        body.role-admin .sidebar-avatar{background:linear-gradient(135deg,#8b5cf6,#7c3aed)!important;}
        body.role-teacher .sidebar-avatar{background:linear-gradient(135deg,#10b981,#059669)!important;}
        body.role-student .sidebar-avatar{background:linear-gradient(135deg,#2563eb,#4f46e5)!important;}
        body.role-admin .sidebar-pname, body.role-teacher .sidebar-pname, body.role-student .sidebar-pname{font-weight:800!important;font-size:.95rem!important;margin-bottom:.25rem!important;line-height:1.25!important;}
        body.role-admin .sidebar-prole, body.role-teacher .sidebar-prole, body.role-student .sidebar-prole{display:inline-block!important;padding:.22rem .7rem!important;border-radius:999px!important;font-size:.7rem!important;font-weight:800!important;letter-spacing:.04em!important;text-transform:uppercase!important;}
        body.role-admin .sidebar-prole{background:rgba(139,92,246,.16)!important;color:#ddd6fe!important;border:1px solid rgba(167,139,250,.35)!important;}
        body.role-teacher .sidebar-prole{background:rgba(16,185,129,.16)!important;color:#bbf7d0!important;border:1px solid rgba(16,185,129,.35)!important;}
        body.role-student .sidebar-prole{background:rgba(37,99,235,.16)!important;color:#bfdbfe!important;border:1px solid rgba(96,165,250,.35)!important;}
        body.role-admin .nav-section-label, body.role-teacher .nav-section-label, body.role-student .nav-section-label{color:rgba(255,255,255,.42)!important;-webkit-text-fill-color:rgba(255,255,255,.42)!important;}
        body.role-admin .sidebar-nav a, body.role-admin .sidebar-nav .nav-item,
        body.role-teacher .sidebar-nav a, body.role-teacher .sidebar-nav .nav-item,
        body.role-student .sidebar-nav a, body.role-student .sidebar-nav .nav-item,
        body.role-admin .sidebar-bottom a, body.role-teacher .sidebar-bottom a, body.role-student .sidebar-bottom a{
            color:rgba(255,255,255,.68)!important;-webkit-text-fill-color:rgba(255,255,255,.68)!important;background:transparent!important;border:1px solid transparent!important;
        }
        body.role-admin .sidebar-nav a:hover, body.role-admin .sidebar-nav .nav-item:hover,
        body.role-teacher .sidebar-nav a:hover, body.role-teacher .sidebar-nav .nav-item:hover,
        body.role-student .sidebar-nav a:hover, body.role-student .sidebar-nav .nav-item:hover,
        body.role-admin .sidebar-bottom a:hover, body.role-teacher .sidebar-bottom a:hover, body.role-student .sidebar-bottom a:hover{
            background:rgba(255,255,255,.08)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;
        }
        body.role-admin .sidebar-nav a.active, body.role-admin .sidebar-nav .nav-item.active,
        body.role-teacher .sidebar-nav a.active, body.role-teacher .sidebar-nav .nav-item.active,
        body.role-student .sidebar-nav a.active, body.role-student .sidebar-nav .nav-item.active{
            background:rgba(59,130,246,.20)!important;color:#93c5fd!important;-webkit-text-fill-color:#93c5fd!important;border-color:rgba(59,130,246,.35)!important;
        }
        body.role-admin .sidebar svg, body.role-teacher .sidebar svg, body.role-student .sidebar svg{color:currentColor!important;stroke:currentColor!important;}
    `;
    document.head.appendChild(s);
}

function renderRoleSidebarNav() {
    const role = (typeof getRole === 'function') ? getRole() : null;
    const nav = document.querySelector('.sidebar-nav');
    const items = roleNavItemsFor(role);
    if (!nav || !items) return;

    document.body.classList.add(`role-${role}`);
    injectRoleSidebarStyles();

    // IMPORTANT: admin-dashboard.html and teacher-dashboard.html have their own
    // section switchers (loadSection/showSection) wired to native buttons.
    // Replacing their sidebar with generated <a> links caused hash changes,
    // broken active states and sections stuck on “Огляд”. On native dashboards
    // we keep the original markup and only refresh profile/styles. Shared pages
    // such as profile.html, schedule.html and questions pages still get the
    // role-aware sidebar.
    if (isNativeDashboardPage()) {
        updateRoleSidebarActive();
        return;
    }

    const html = items.map(it => {
        if (it.type === 'label') return `<div class="nav-section-label">${escapeHtml(it.text)}</div>`;
        return `<a class="nav-item role-nav-link" href="${it.href}">${roleNavIcon(it.icon)}<span>${escapeHtml(it.label)}</span></a>`;
    }).join('');
    nav.innerHTML = html;
    updateRoleSidebarActive();
}

async function ensureRoleSidebarProfile() {
    const role = (typeof getRole === 'function') ? getRole() : null;
    if (role !== 'admin' && role !== 'teacher' && role !== 'student') return;
    const sidebar = document.querySelector('.sidebar');
    const logo = document.querySelector('.sidebar-logo');
    if (!sidebar || !logo) return;
    document.body.classList.add(`role-${role}`);
    injectRoleSidebarStyles();

    let profile = sidebar.querySelector('.sidebar-profile');
    if (!profile) {
        profile = document.createElement('div');
        profile.className = 'sidebar-profile';
        logo.insertAdjacentElement('afterend', profile);
    }
    const fallbackName = role === 'admin' ? 'Адміністратор' : role === 'teacher' ? 'Викладач' : 'Студент';
    const fallbackInitials = role === 'admin' ? 'АД' : role === 'teacher' ? 'ВК' : 'СТ';
    profile.innerHTML = `
        <div class="sidebar-avatar" id="roleSidebarAvatar">${fallbackInitials}</div>
        <div class="sidebar-pname" id="roleSidebarName">${fallbackName}</div>
        <span class="sidebar-prole role-${role}" id="roleSidebarBadge">${roleLabel(role)}</span>
    `;
    try {
        // Use the real /api/users/me helper. A previous version called an
        // undefined getCurrentUser(), so the sidebar silently kept fallback
        // values such as “Викладач / ВК” while the profile card showed the
        // real user data. Keep a small cache to avoid duplicate requests.
        const user = window.__roleSidebarUser || await fetchCurrentUser();
        window.__roleSidebarUser = user;
        const name = user?.full_name || user?.email || fallbackName;
        const email = user?.email || '';
        const initials = initialsFromName(name, email);
        profile.querySelector('#roleSidebarAvatar').textContent = initials;
        profile.querySelector('#roleSidebarName').textContent = name;
        if (role === 'admin') {
            const el = document.getElementById('adminName');
            if (el) el.textContent = name;
            const av = document.getElementById('adminAvatar');
            if (av) av.textContent = initials;
        }
        if (role === 'teacher') {
            const el = document.getElementById('teacherName');
            if (el) el.textContent = name;
            const av = document.getElementById('teacherAvatar');
            if (av) av.textContent = initials;
        }
        if (role === 'student') {
            const el = document.getElementById('studentName');
            if (el) el.textContent = name;
            const av = document.getElementById('studentAvatar');
            if (av) av.textContent = initials;
        }
    } catch (err) {
        console.warn('Role sidebar profile could not be refreshed', err);
        // The page should not break if /api/users/me is temporarily unavailable.
    }
}

function updateRoleSidebarActive() {
    const role = (typeof getRole === 'function') ? getRole() : null;
    const items = roleNavItemsFor(role);
    const nav = document.querySelector('.sidebar-nav');
    if (!nav || !items) return;

    const page = currentRolePage();
    const hash = location.hash || '#overview';
    const links = [...nav.querySelectorAll('.nav-item')];
    links.forEach(link => link.classList.remove('active'));

    // Native dashboard sidebars use data-section/onclick buttons.
    // Generated/shared sidebars use href links. Support both shapes.
    links.forEach(link => {
        const href = (link.getAttribute('href') || '').toLowerCase();
        const onclick = link.getAttribute('onclick') || '';
        const dataSection = (link.getAttribute('data-section') || '').trim();
        let active = false;
        if (dataSection) {
            const sectionHash = `#${dataSection}`;
            active = hash === sectionHash || (!location.hash && dataSection === 'overview');
        } else if (href) {
            const [targetPage, targetHashRaw=''] = href.split('#');
            const targetHash = targetHashRaw ? `#${targetHashRaw}` : '';
            active = (targetPage === page || (!targetPage && page)) && (!targetHash || targetHash === hash);
        }
        const m = onclick.match(/(?:loadSection|showSection)\(['"]([^'"]+)['"]\)/);
        if (!dataSection && m) {
            const sectionHash = `#${m[1]}`;
            active = hash === sectionHash || (!location.hash && m[1] === 'overview');
        }
        if (active) link.classList.add('active');
    });
}
window.updateRoleSidebarActive = updateRoleSidebarActive;

function bindRoleSidebarNavigation() {
    if (window.__roleSidebarNavigationBound) return;
    window.__roleSidebarNavigationBound = true;
    document.addEventListener('click', async (e) => {
        const link = e.target.closest && e.target.closest('.role-nav-link');
        if (!link) return;
        const href = link.getAttribute('href') || '';
        if (!href) return;
        const [targetPageRaw, targetHashRaw=''] = href.split('#');
        const targetPage = (targetPageRaw || currentRolePage()).toLowerCase();
        const sectionId = String(targetHashRaw || '').replace('#', '').trim();
        const currentPage = currentRolePage();
        const samePage = targetPage === currentPage;
        if (samePage && sectionId) {
            e.preventDefault();
            e.stopImmediatePropagation();
            history.replaceState(null, '', `${targetPage}#${sectionId}`);
            // Admin dashboard exposes loadSection(); teacher dashboard exposes
            // showSection(). Support both APIs and fall back to a hashchange event.
            try {
                if (typeof window.loadSection === 'function') {
                    await window.loadSection(sectionId, false);
                } else if (typeof window.showSection === 'function') {
                    window.showSection(sectionId, false);
                } else {
                    window.dispatchEvent(new HashChangeEvent('hashchange'));
                }
            } catch (err) {
                console.warn('Role sidebar navigation failed', err);
                window.location.href = href;
                return;
            }
            updateRoleSidebarActive();
        }
    }, true);
}

function redirectStaffAwayFromStudentPages() {
    const role = (typeof getRole === 'function') ? getRole() : null;
    if (!role || role === 'student') return;
    const page = currentRolePage();
    if (page === 'courses.html') {
        window.location.replace(role === 'admin' ? 'admin-dashboard.html#courses' : 'teacher-dashboard.html#courses');
    }
    if (page === 'questions.html') {
        window.location.replace(role === 'admin' ? 'admin-questions.html' : 'teacher-questions.html');
    }
}

function initRoleSidebarConsistency() {
    try {
        redirectStaffAwayFromStudentPages();
        renderRoleSidebarNav();
        ensureRoleSidebarProfile();
        bindRoleSidebarNavigation();
        setTimeout(updateRoleSidebarActive, 0);
        setTimeout(updateRoleSidebarActive, 250);
    } catch (e) {
        console.warn('Role sidebar consistency failed', e);
    }
}

document.addEventListener('DOMContentLoaded', initRoleSidebarConsistency);
window.addEventListener('hashchange', updateRoleSidebarActive);

// ─── Export Reports (Teacher) ────────────────────────────────────────

/** Convert report data to CSV format */
function reportToCSV(report) {
    if (!report || !report.columns || !report.rows) {
        return 'Немає даних';
    }
    
    const headers = report.columns;
    const rows = report.rows.map(row => 
        headers.map(col => {
            const cell = row[col];
            const cellStr = cell === null || cell === undefined ? '' : String(cell);
            // Escape quotes and wrap in quotes if needed
            return cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')
                ? `"${cellStr.replace(/"/g, '""')}"` 
                : cellStr;
        }).join(',')
    );
    
    return [headers.join(','), ...rows].join('\n');
}

/** Export and download report as CSV */
async function exportReport(reportType) {
    try {
        const report = await fetchReportData(reportType);
        
        if (!report) {
            showToast('Помилка: не вдалося отримати дані звіту', 'error');
            return;
        }
        
        // Convert to CSV
        const csvContent = reportToCSV(report);
        
        // Generate filename based on report type and timestamp
        const reportNames = {
            'attendance': 'Відвідуваність',
            'task_completion': 'Виконання-завдань',
            'teacher_subject_mapping': 'Викладачі-курси',
            'course_statistics': 'Статистика-курсів',
            'active_students': 'Активні-студенти',
            'graduated_students': 'Випускники',
            'excellent_students': 'Відмінники'
        };
        
        const reportName = reportNames[reportType] || 'Звіт';
        const timestamp = new Date().toISOString().slice(0, 10);
        const filename = `${reportName}_${timestamp}.csv`;
        
        // Trigger download
        downloadFile(csvContent, filename, 'text/csv;charset=utf-8;');
        
        showToast(`Звіт "${report.title}" скачано!`, 'success');
        return report;
    } catch (error) {
        console.error('Export error:', error);
        showToast(`Помилка: ${error.message}`, 'error');
    }
}

function generateAttendanceCSV(students) {
    const headers = ['Студент', 'Email', 'Група', 'Середня оцінка', 'Відвідуваність', 'Telegram'];
    const rows = students.map(s => [
        s.full_name,
        s.email,
        s.group,
        s.avg_grade + '%',
        s.attendance + '%',
        s.telegram_linked ? 'Так' : 'Ні'
    ]);
    
    const csv = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');
    
    return csv;
}

function downloadFile(content, filename, mimeType) {
    const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }, 100);
}

window.addEventListener('load', () => {
    // Only init if token exists (we use role from localStorage)
    if (getToken()) {
        setTimeout(initStudentChatWidget, 500);
    }
});

// ─── Structured Questions + Notifications helpers ───────────────────
async function fetchMyQuestions() { return apiGet('/api/questions/my'); }
async function fetchTeacherQuestions() { return apiGet('/api/questions/teacher'); }
async function fetchAdminQuestions(targetType = '') {
    const suffix = targetType ? `?target_type=${encodeURIComponent(targetType)}` : '';
    return apiGet(`/api/questions/admin${suffix}`);
}
async function createQuestion(payload) { return apiPost('/api/questions', payload); }
async function replyQuestion(threadId, message) { return apiPost(`/api/questions/${threadId}/reply`, { message }); }
async function closeQuestion(threadId) { return apiPatch(`/api/questions/${threadId}/close`, {}); }
async function assignQuestion(threadId, payload) { return apiPatch(`/api/questions/${threadId}/assign`, payload); }
async function fetchNotifications(unreadOnly = false) { return apiGet(`/api/notifications${unreadOnly ? '?unread_only=true' : ''}`); }
async function markAllNotificationsRead() { return apiPatch('/api/notifications/read-all', {}); }

function notificationDestinationForRole(role) {
    if (role === 'admin') return 'admin-questions.html';
    if (role === 'teacher') return 'teacher-questions.html';
    return 'questions.html';
}

function initGlobalNotificationsBell() {
    // Remove the old floating bell if a browser cached it from earlier builds.
    const oldFloating = document.getElementById('globalNotificationBell');
    if (oldFloating) oldFloating.remove();

    if (!getToken()) return;

    const ensureStyles = () => {
        if (document.getElementById('notificationBadgeStyles')) return;
        const st = document.createElement('style');
        st.id = 'notificationBadgeStyles';
        st.textContent = `
            .nav-notification-badge{
                display:inline-flex;align-items:center;justify-content:center;
                min-width:1.35rem;height:1.35rem;padding:0 .36rem;margin-left:auto;
                border-radius:999px;background:#2563eb;color:#fff!important;
                font-size:.72rem;font-weight:800;line-height:1;box-shadow:0 0 0 2px rgba(37,99,235,.18);
            }
            .nav-item .nav-notification-badge,.sidebar-nav a .nav-notification-badge{margin-left:auto;}
            .nav-unread-pulse{position:relative;}
            .nav-unread-pulse::after{content:'';position:absolute;right:.65rem;top:.65rem;width:.45rem;height:.45rem;border-radius:999px;background:#60a5fa;}
        `;
        document.head.appendChild(st);
    };

    const removeBadges = () => {
        document.querySelectorAll('.nav-notification-badge').forEach(x => x.remove());
        document.querySelectorAll('.nav-unread-pulse').forEach(x => x.classList.remove('nav-unread-pulse'));
    };

    const targetHref = notificationDestinationForRole(getRole());
    const updateBadges = async () => {
        try {
            const unread = await fetchNotifications(true);
            const count = Array.isArray(unread) ? unread.length : 0;
            ensureStyles();
            removeBadges();
            if (!count) return;

            const links = Array.from(document.querySelectorAll('a[href]')).filter(a => {
                const href = (a.getAttribute('href') || '').split('#')[0];
                return href === targetHref;
            });
            links.forEach(link => {
                link.classList.add('nav-unread-pulse');
                const badge = document.createElement('span');
                badge.className = 'nav-notification-badge';
                badge.textContent = count > 99 ? '99+' : String(count);
                link.appendChild(badge);
            });
        } catch (e) {
            // Never break the page because notifications failed.
            console.warn('Notifications badge failed:', e);
        }
    };

    if (window.__itSchoolNotificationTimer) clearInterval(window.__itSchoolNotificationTimer);
    updateBadges();
    window.__itSchoolNotificationTimer = setInterval(updateBadges, 30000);
}

window.addEventListener('load', () => {
    initGlobalNotificationsBell();
});
