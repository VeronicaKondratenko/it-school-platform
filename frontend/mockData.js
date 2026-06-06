const MOCK_DATA = {

    // ── AUTH ──────────────────────────────────────────────────────────
    'student': {
        id: 1, 
        full_name: 'Test Student', 
        email: 'student@example.com',
        patronymic: 'Петрович',
        date_of_birth: '2004-05-12',
        phone: '+380501112233',
        photo_url: null,
        role: 'student', 
        telegram_id: 123456789,
        groups: [
            { id: 1, name: 'WEB-2024-A', course_ids: [1], teacher_id: 2, is_active: true },
            { id: 2, name: 'DB-2024-B',  course_ids: [2], teacher_id: 3, is_active: true }
        ],
        study_groups: [
            { id: 1, name: 'WEB-2024-A', course_ids: [1], teacher_id: 2, is_active: true },
            { id: 2, name: 'DB-2024-B',  course_ids: [2], teacher_id: 3, is_active: true }
        ]
    },
    'teacher': {
        id: 2, full_name: 'Ivan Ivanov', email: 'teacher@example.com',
        patronymic: 'Іванович', date_of_birth: '1990-02-20', phone: '+380507778899', photo_url: null,
        role: 'teacher', telegram_id: null, study_groups: []
    },
    'admin': {
        id: 1, full_name: 'System Admin', email: 'admin@school.com',
        patronymic: 'Адміністраторович', date_of_birth: '1988-01-01', phone: '+380500000000', photo_url: null,
        role: 'admin', telegram_id: null, study_groups: []
    },

    // ── /api/users/me (returned by role) ──────────────────────────────
    '/api/users/me': null, // set at runtime by mockLogin()

    // ── /api/courses ──────────────────────────────────────────────────
    '/api/courses': [
        { id: 1, title: 'Веб-розробка',        description: 'HTML, CSS, JavaScript та сучасні фреймворки' },
        { id: 2, title: 'Бази даних',           description: 'SQL, NoSQL, проектування та оптимізація' },
        { id: 3, title: 'Алгоритми',            description: 'Структури даних та алгоритми програмування' },
        { id: 4, title: 'UI/UX Дизайн',         description: 'Figma, прототипування та дизайн-системи' },
        { id: 5, title: 'Python',               description: 'Основи Python, OOP та машинне навчання' },
        { id: 6, title: 'Дискретна математика', description: 'Теорія графів, комбінаторика, логіка' }
    ],

    // ── /api/disciplines ─────────────────────────────────────────────
    '/api/disciplines': [
        { id: 1, name: 'Веб-розробка', course_id: 1, course_title: 'Веб-розробка' },
        { id: 2, name: 'Бази даних', course_id: 2, course_title: 'Бази даних' },
        { id: 3, name: 'Алгоритми', course_id: 3, course_title: 'Алгоритми' },
        { id: 4, name: 'UI/UX Дизайн', course_id: 4, course_title: 'UI/UX Дизайн' },
        { id: 5, name: 'Python', course_id: 5, course_title: 'Python' },
        { id: 6, name: 'Дискретна математика', course_id: 6, course_title: 'Дискретна математика' }
    ],

    // ── /api/groups ───────────────────────────────────────────────────
    '/api/groups': [
        { id: 1, name: 'WEB-2024-A', course_ids: [1], teacher_id: 2, is_active: true },
        { id: 2, name: 'DB-2024-B',  course_ids: [2], teacher_id: 3, is_active: true },
        { id: 3, name: 'ALG-2024-C', course_ids: [3], teacher_id: 2, is_active: true },
        { id: 4, name: 'PY-2024-D',  course_ids: [5], teacher_id: 3, is_active: false }
    ],

    '/api/teacher/courses': [
        { id: 1, title: 'Веб-розробка', description: 'HTML, CSS, JavaScript та сучасні фреймворки' },
        { id: 3, title: 'Алгоритми', description: 'Структури даних та алгоритми програмування' }
    ],

    // ── /api/schedule ─────────────────────────────────────────────────
    '/api/schedule': [
        // Monday 23 March
        { id: 1, date: '2026-03-23', time: '08:00:00', end_time: '09:30:00', group_id: 1, teacher_id: 2, discipline_id: 1, discipline_name: 'Веб-розробка',  group_name: 'WEB-2024-A', color: '#2563eb', meeting_link: 'https://meet.google.com/abc-defg-hij' },
        { id: 8, date: '2026-03-23', time: '09:45:00', end_time: '11:15:00', group_id: 2, teacher_id: 3, discipline_id: 2, discipline_name: 'Бази даних',    group_name: 'DB-2024-B',  color: '#10b981', meeting_link: 'https://zoom.us/j/123456789' },
        { id: 9, date: '2026-03-23', time: '11:30:00', end_time: '13:00:00', group_id: 3, teacher_id: 2, discipline_id: 3, discipline_name: 'Алгоритми',     group_name: 'ALG-2024-C', color: '#f59e0b', meeting_link: null },
        { id: 4, date: '2026-03-23', time: '14:00:00', end_time: '15:30:00', group_id: 1, teacher_id: 2, discipline_id: 1, discipline_name: 'Веб-розробка',  group_name: 'WEB-2024-A', color: '#2563eb', meeting_link: 'https://meet.google.com/xyz-uvwx-yz' },
        
        // Tuesday 24 March
        { id: 2, date: '2026-03-24', time: '08:00:00', end_time: '09:30:00', group_id: 2, teacher_id: 3, discipline_id: 2, discipline_name: 'Бази даних',    group_name: 'DB-2024-B',  color: '#10b981', meeting_link: 'https://zoom.us/j/987654321' },
        { id: 5, date: '2026-03-24', time: '09:45:00', end_time: '11:15:00', group_id: 3, teacher_id: 2, discipline_id: 3, discipline_name: 'Алгоритми',     group_name: 'ALG-2024-C', color: '#f59e0b', meeting_link: 'https://zoom.us/j/987654321' },
        { id: 10, date: '2026-03-24', time: '11:30:00', end_time: '13:00:00', group_id: 1, teacher_id: 2, discipline_id: 1, discipline_name: 'Веб-розробка',  group_name: 'WEB-2024-A', color: '#2563eb', meeting_link: 'https://meet.google.com/frontend-js' },
        
        // Wednesday 25 March
        { id: 3, date: '2026-03-25', time: '08:00:00', end_time: '09:30:00', group_id: 3, teacher_id: 2, discipline_id: 3, discipline_name: 'Алгоритми',     group_name: 'ALG-2024-C', color: '#f59e0b', meeting_link: null },
        { id: 11, date: '2026-03-25', time: '12:30:00', end_time: '14:00:00', group_id: 2, teacher_id: 3, discipline_id: 2, discipline_name: 'Бази даних',    group_name: 'DB-2024-B',  color: '#10b981', meeting_link: 'https://zoom.us/j/555666777' },
        
        // Thursday 26 March
        { id: 6, date: '2026-03-26', time: '11:30:00', end_time: '13:00:00', group_id: 2, teacher_id: 3, discipline_id: 2, discipline_name: 'Бази даних',    group_name: 'DB-2024-B',  color: '#10b981', meeting_link: 'https://meet.google.com/qwe-rtyui-op' },
        { id: 12, date: '2026-03-26', time: '14:00:00', end_time: '15:30:00', group_id: 1, teacher_id: 2, discipline_id: 1, discipline_name: 'Веб-розробка',  group_name: 'WEB-2024-A', color: '#2563eb', meeting_link: 'https://zoom.us/j/111222333' },
        
        // Friday 27 March
        { id: 7, date: '2026-03-27', time: '14:00:00', end_time: '15:30:00', group_id: 5, teacher_id: 2, discipline_id: 1, discipline_name: 'Веб-розробка',  group_name: 'WEB-2024-A', color: '#2563eb', meeting_link: 'https://zoom.us/j/555666777' },
        { id: 13, date: '2026-03-27', time: '08:00:00', end_time: '09:30:00', group_id: 3, teacher_id: 2, discipline_id: 3, discipline_name: 'Алгоритми',     group_name: 'ALG-2024-C', color: '#f59e0b', meeting_link: 'https://meet.google.com/algorithms-course' }
    ],

    // ── /api/admin/users ──────────────────────────────────────────────
    '/api/admin/users': [
        { id: 1, full_name: 'Іван Петренко',   email: 'student@example.com',  role: 'student',  telegram_id: 123456789, is_active: true, phone: '+380501112233', study_groups: [{name:'WEB-2024-A'},{name:'DB-2024-B'}] },
        { id: 2, full_name: 'Олексій Ковальчук', email: 'teacher@example.com', role: 'teacher',  telegram_id: null, is_active: true, phone: '+380507778899', study_groups: [] },
        { id: 3, full_name: 'Адміністратор',   email: 'admin@example.com',    role: 'admin',    telegram_id: null, is_active: true, phone: '+380500000000', study_groups: [] },
        { id: 4, full_name: 'Марія Сидоренко', email: 'maria@example.com',    role: 'student',  telegram_id: 987654321, is_active: true, phone: '+380502223344', study_groups: [{name:'WEB-2024-A'}] },
        { id: 5, full_name: 'Петро Мельник',   email: 'petro@example.com',    role: 'student',  telegram_id: null, is_active: false, phone: '+380503335566', study_groups: [{name:'ALG-2024-C'}] },
        { id: 6, full_name: 'Анна Шевченко',   email: 'anna@example.com',     role: 'teacher',  telegram_id: null, is_active: true, phone: '+380504446677', study_groups: [] },
        { id: 7, full_name: 'Дмитро Бондаренко', email: 'dmytro@example.com', role: 'student',  telegram_id: 111222333, is_active: true, phone: '+380505557788', study_groups: [{name:'DB-2024-B'},{name:'PY-2024-D'}] },
        { id: 8, full_name: 'Олена Тимченко',  email: 'olena@example.com',    role: 'student',  telegram_id: null, is_active: true, phone: '+380506668899', study_groups: [{name:'ALG-2024-C'}] }
    ],

    // ── /api/admin/stats ──────────────────────────────────────────────
    '/api/admin/stats': {
        total_users: 8,
        total_students: 5,
        total_teachers: 2,
        total_courses: 6,
        total_groups: 4,
        active_groups: 3,
        total_schedules: 13,
        telegram_linked: 4
    },

    // ── /api/messages/inbox (teacher) ────────────────────────────────
    '/api/messages/inbox': [
        {
            id: 1, sender_name: 'Іван Петренко', sender_email: 'student@example.com',
            content: 'Як зареєструватися на іспит? Де це можна зробити на сайті?',
            timestamp: '2026-03-22T18:30:00', status: 'pending', is_escalated: true,
            telegram_id: 123456789
        },
        {
            id: 2, sender_name: 'Марія Сидоренко', sender_email: 'maria@example.com',
            content: 'Маю питання щодо оплати за наступний семестр. Куди звернутись та які терміни?',
            timestamp: '2026-03-22T20:15:00', status: 'pending', is_escalated: true,
            telegram_id: 987654321
        },
        {
            id: 3, sender_name: 'Петро Мельник', sender_email: 'petro@example.com',
            content: 'Не можу зайти до кабінету студента — пише "невірний пароль". Можна скинути?',
            timestamp: '2026-03-23T09:00:00', status: 'pending', is_escalated: true,
            telegram_id: null
        },
        {
            id: 4, sender_name: 'Дмитро Бондаренко', sender_email: 'dmytro@example.com',
            content: 'Як записатися в групу Python? Бачу курс на сайті але немає кнопки.',
            timestamp: '2026-03-23T11:30:00', status: 'answered', is_escalated: true,
            telegram_id: 111222333, reply: 'Зверніться до адміністратора або викладача для запису.'
        }
    ],

    // ── /api/messages/public ────────────────────────────────────────
    '/api/messages/public': [
        {
            id: 2001,
            title: 'Зміни в розкладі',
            message: 'Завтра заняття з веб-розробки почнеться на 30 хвилин пізніше.',
            sender_name: 'Ivan Ivanov',
            timestamp: '2026-03-26T16:00:00',
            target_role: 'student'
        },
        {
            id: 2002,
            title: 'Нове матеріали курсу',
            message: 'До теми по SQL додано нову презентацію та приклади.',
            sender_name: 'Ivan Ivanov',
            timestamp: '2026-03-25T10:30:00',
            target_role: 'student'
        }
    ],

    // ── /api/student/notifications ─────────────────────────────────
    '/api/student/notifications': [
        {
            id: 2001,
            title: 'Зміни в розкладі',
            message: 'Завтра заняття з веб-розробки почнеться на 30 хвилин пізніше.',
            sender_name: 'Ivan Ivanov',
            timestamp: '2026-03-26T16:00:00',
            target_role: 'student'
        },
        {
            id: 2002,
            title: 'Нове матеріали курсу',
            message: 'До теми по SQL додано нову презентацію та приклади.',
            sender_name: 'Ivan Ivanov',
            timestamp: '2026-03-25T10:30:00',
            target_role: 'student'
        }
    ],

    // ── /api/course_topics ──────────────────────────────────────────
    '/api/course_topics': [
        { id: 11, course_id: 1, discipline_id: 1, title: 'HTML основи', discipline_name: 'Веб-розробка' },
        { id: 12, course_id: 1, discipline_id: 1, title: 'CSS layouts', discipline_name: 'Веб-розробка' },
        { id: 21, course_id: 2, discipline_id: 2, title: 'SELECT та JOIN', discipline_name: 'Бази даних' },
        { id: 22, course_id: 2, discipline_id: 2, title: 'Нормалізація', discipline_name: 'Бази даних' },
        { id: 31, course_id: 3, discipline_id: 3, title: 'Сортування', discipline_name: 'Алгоритми' },
        { id: 32, course_id: 3, discipline_id: 3, title: 'Пошук', discipline_name: 'Алгоритми' }
    ],

    // ── /api/assignments (student) ────────────────────────────────────
    // ALL assignments (for admin/teacher views)
    '/api/assignments': [
        { id: 1, title: 'Створити лендінг на HTML/CSS', description: 'Зверстати адаптивну сторінку', due_date: '2026-03-28', topic_id: 11, discipline_name: 'Веб-розробка', course_name: 'Веб-розробка', max_score: 100 },
        { id: 2, title: 'SQL запити — Практична робота', description: 'Написати 15 складних запитів', due_date: '2026-03-25', topic_id: 21, discipline_name: 'Бази даних', course_name: 'Бази даних', max_score: 100 },
        { id: 3, title: 'Алгоритм сортування злиттям', description: 'Реалізувати Merge Sort на Python', due_date: '2026-03-22', topic_id: 31, discipline_name: 'Алгоритми', course_name: 'Алгоритми', max_score: 100 },
        { id: 4, title: 'Прототип мобільного додатку', description: 'Figma макет — 5 екранів', due_date: '2026-04-01', topic_id: 41, discipline_name: 'UI/UX Дизайн', course_name: 'UI/UX Дизайн', max_score: 100 },
        { id: 5, title: 'Класи та об\'єкти Python', description: 'ООП практика', due_date: '2026-03-30', topic_id: 51, discipline_name: 'Python', course_name: 'Python', max_score: 100 }
    ],

    '/api/assignment_submissions': [
        { submission_id: 1001, id: 1001, assignment_id: 1, student_id: 1, student_name: 'Іван Петренко', content: 'Посилання на GitHub: https://github.com/demo/landing', file_name: 'landing.zip', is_locked: true, grade_status: 'submitted', grade_score: null, grade_feedback: null, submitted_at: '2026-03-26T09:30:00' },
        { submission_id: 1002, id: 1002, assignment_id: 2, student_id: 4, student_name: 'Марія Сидоренко', content: 'SQL script attached', file_name: 'queries.sql', is_locked: true, grade_status: 'graded', grade_score: 88, grade_feedback: 'Добре, перевір JOIN', submitted_at: '2026-03-24T13:10:00' },
        { submission_id: 1003, id: 1003, assignment_id: 3, student_id: 5, student_name: 'Петро Мельник', content: 'Merge sort implementation', file_name: 'merge_sort.py', is_locked: false, grade_status: 'reviewed', grade_score: null, grade_feedback: 'Потрібно оптимізувати', submitted_at: '2026-03-22T18:20:00' }
    ],

    // ── /api/student/assignments (for student - only from enrolled courses) ──
    // Студент Іван Петренко записаний на: Веб-розробка (1) та Бази даних (2)
    '/api/student/assignments': [
        {
            id: 1,
            title: 'Створити лендінг на HTML/CSS',
            description: 'Зверстати адаптивну сторінку з фіксованою та гнучкою версіями',
            due_date: '2026-03-28',
            topic_id: 1,
            discipline_name: 'Веб-розробка',
            course_id: 1,
            status: 'pending',
            priority: 'high',
            submission_locked: false,
            submission_file_name: null,
            submission_content: null,
            grade_status: null,
            grade_score: null,
            grade_feedback: null
        },
        {
            id: 2,
            title: 'Практична робота — SQL запити',
            description: 'Написати 15 складних SELECT запитів з JOIN та GROUP BY',
            due_date: '2026-03-25',
            topic_id: 2,
            discipline_name: 'Бази даних',
            course_id: 2,
            status: 'submitted',
            priority: 'high',
            submission_locked: true,
            submission_file_name: 'queries.sql',
            submission_content: 'SQL script attached',
            grade_status: null,
            grade_score: null,
            grade_feedback: null
        },
        {
            id: 5,
            title: 'Лабораторна 3 — CSS Flexbox та Grid',
            description: 'Створити адаптивний макет для портфоліо',
            due_date: '2026-04-02',
            topic_id: 1,
            discipline_name: 'Веб-розробка',
            course_id: 1,
            status: 'pending',
            priority: 'medium',
            submission_locked: false,
            submission_file_name: null,
            submission_content: null,
            grade_status: null,
            grade_score: null,
            grade_feedback: null
        },
        {
            id: 6,
            title: 'Практична 3 — Індекси та оптимізація',
            description: 'Оптимізувати запити за допомогою індексів',
            due_date: '2026-03-31',
            topic_id: 2,
            discipline_name: 'Бази даних',
            course_id: 2,
            status: 'pending',
            priority: 'medium',
            submission_locked: false,
            submission_file_name: null,
            submission_content: null,
            grade_status: null,
            grade_score: null,
            grade_feedback: null
        }
    ],

    // ── /api/grades (student) ─────────────────────────────────────────
    '/api/grades': [
        { discipline: 'Веб-розробка',        assignment: 'Лабораторна 1 — HTML структура',  grade: 95, max_grade: 100, date: '2026-03-10' },
        { discipline: 'Веб-розробка',        assignment: 'Лабораторна 2 — CSS стилі',       grade: 88, max_grade: 100, date: '2026-03-15' },
        { discipline: 'Бази даних',          assignment: 'Практична 1 — SELECT запити',     grade: 90, max_grade: 100, date: '2026-03-12' },
        { discipline: 'Алгоритми',           assignment: 'Merge Sort',                       grade: 92, max_grade: 100, date: '2026-03-22' },
        { discipline: 'Дискретна математика', assignment: 'Теорія графів — тест',           grade: 78, max_grade: 100, date: '2026-03-18' }
    ],

    // ── /api/student/courses (student courses with grades) ────────────
    // Студент Іван Петренко записаний на: Веб-розробка (WEB-2024-A) та Бази даних (DB-2024-B)
    '/api/student/courses': [
        {
            course_id: 1,
            course_title: 'Веб-розробка',
            grades: [
                {
                    id: 1,
                    score: 95,
                    feedback: 'Відмінна робота! Хороша структура.',
                    graded_at: '2026-03-10T14:30:00',
                    assignment: { id: 1, title: 'Лабораторна 1 — HTML структура', description: 'Правильно структуровано', due_date: '2026-03-08', topic_id: 1 }
                },
                {
                    id: 2,
                    score: 88,
                    feedback: 'Добре, але треба покращити мобільну адаптацію.',
                    graded_at: '2026-03-15T10:15:00',
                    assignment: { id: 2, title: 'Лабораторна 2 — CSS стилі', description: 'Оформлення та адаптивність', due_date: '2026-03-13', topic_id: 1 }
                },
                {
                    id: 5,
                    score: 92,
                    feedback: 'Добра реалізація JavaScript функцій.',
                    graded_at: '2026-03-20T16:00:00',
                    assignment: { id: 5, title: 'Практична 3 — JavaScript DOM', description: 'Маніпуляція з DOM', due_date: '2026-03-18', topic_id: 1 }
                }
            ],
            average_score: 91.67,
            grades_count: 3,
            enrolled_students_count: 2
        },
        {
            course_id: 2,
            course_title: 'Бази даних',
            grades: [
                {
                    id: 3,
                    score: 90,
                    feedback: 'Правильні запити! Оптимізуй JOIN.',
                    graded_at: '2026-03-12T11:45:00',
                    assignment: { id: 3, title: 'Практична 1 — SELECT запити', description: 'Написання SQL запитів', due_date: '2026-03-10', topic_id: 2 }
                },
                {
                    id: 6,
                    score: 85,
                    feedback: 'Хорошо, но есть ошибки в нормализации.',
                    graded_at: '2026-03-19T13:20:00',
                    assignment: { id: 6, title: 'Практична 2 — Нормалізація БД', description: 'Проектування схеми', due_date: '2026-03-17', topic_id: 2 }
                }
            ],
            average_score: 87.5,
            grades_count: 2,
            enrolled_students_count: 2
        }
    ],

    // ── /api/teacher/students (teacher's student list) ────────────────
    '/api/teacher/students': [
        { id: 1, full_name: 'Іван Петренко',   email: 'student@example.com',  group: 'WEB-2024-A', telegram_linked: true,  avg_grade: 91, attendance: 95 },
        { id: 4, full_name: 'Марія Сидоренко', email: 'maria@example.com',    group: 'WEB-2024-A', telegram_linked: true,  avg_grade: 87, attendance: 88 },
        { id: 5, full_name: 'Петро Мельник',   email: 'petro@example.com',    group: 'ALG-2024-C', telegram_linked: false, avg_grade: 75, attendance: 72 },
        { id: 7, full_name: 'Дмитро Бондаренко', email: 'dmytro@example.com', group: 'ALG-2024-C', telegram_linked: true, avg_grade: 82, attendance: 80 },
        { id: 8, full_name: 'Олена Тимченко',  email: 'olena@example.com',    group: 'ALG-2024-C', telegram_linked: false, avg_grade: 93, attendance: 98 }
    ],

    // ── /api/teacher/stats ────────────────────────────────────────────
    '/api/teacher/stats': {
        total_students: 5,
        total_groups: 3,
        pending_assignments: 8,
        overdue_assignments: 2,
        pending_questions: 3,
        avg_attendance: 87
    }
};

// ── Credentials map (demo login) ──────────────────────────────────────
// NOTE: When DEMO_MODE=false, these are ignored. Use credentials from seed.py:
const MOCK_CREDENTIALS = {
    'student@example.com': { password: 'password', role: 'student' },
    'teacher@example.com': { password: 'password', role: 'teacher' },
    'admin@school.com':    { password: 'admin123', role: 'admin' },
    // Backup (if needed):
    'admin@example.com':   { password: 'password', role: 'admin' }
};
