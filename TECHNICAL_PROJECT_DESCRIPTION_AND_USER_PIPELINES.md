# IT School: Technical Description and User Pipelines

## 1. Project scope

IT School is an LMS with three roles:

- student
- teacher
- admin

Main capabilities:

- auth and registration
- course and group management
- assignments, submissions, grading
- schedule management with overlap validation
- reporting (JSON for UI tables)
- optional Telegram integration

## 2. Stack

- Frontend: HTML/CSS/Vanilla JS
- Backend: FastAPI + SQLAlchemy (async)
- DB: PostgreSQL
- Auth: JWT (OAuth2 password flow)
- Optional bot: aiogram

## 3. Data model (current)

### User

Fields:

- `email` (unique)
- `password_hash`
- `full_name`
- `patronymic` (nullable)
- `date_of_birth` (nullable)
- `phone` (nullable)
- `photo_url` (nullable)
- `role` (`student|teacher|admin`)
- `telegram_id` (nullable, unique)

### Course and group

- `Course`: `title`, `description`
- `StudyGroup`: `name`, `teacher_id`, `is_active`
- many-to-many group-course via `group_course_association`
- many-to-many student-group via `student_group_association`

### Assignment and submission

- `Assignment`: `title`, `description`, `due_date`, `topic_id`
- `AssignmentSubmission`:
  - `student_id`, `assignment_id`, `content`, `file_name`
  - `is_locked`
  - `grade_status`, `grade_score`, `grade_feedback`, `graded_at`
  - `submitted_at`
  - unique pair `(student_id, assignment_id)`

### Schedule

- `Schedule`: `date`, `time`, `end_time`, `group_id`, `teacher_id`, `discipline_id`, `meeting_link`

## 4. Auth and RBAC

### Public

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/courses`
- `GET /api/schedule`

### Registration rule

Public registration cannot create teachers.
Teacher accounts are created by admin only.

### Admin-only

- `POST /api/groups`
- `POST /api/groups/{group_id}/enroll/{student_id}`
- `POST /api/groups/{group_id}/courses/{course_id}`
- `POST /api/schedule`
- `PUT /api/schedule/{schedule_id}`
- `POST|PUT|DELETE /api/courses/*` (create also available for teacher)
- `GET|POST|PUT|DELETE /api/admin/users*`

### Teacher

- can create courses
- can view students and groups
- can grade/reset submissions
- can edit own profile (`PUT /api/users/me`)

### Student

- can view assignments and courses assigned via admin-managed group enrollment
- can submit assignment once until teacher reset

## 5. API contracts (key)

### Auth

- `POST /api/auth/login`
- `POST /api/auth/register`

### Profile

- `GET /api/users/me`
- `PUT /api/users/me`

### Assignments

- `GET /api/assignments`
- `POST /api/assignments/{assignment_id}/submit`
- `GET /api/assignments/{assignment_id}/submissions`
- `POST /api/assignments/submissions/{submission_id}/grade`
- `POST /api/assignments/submissions/{submission_id}/reset`

### Student aggregates

- `GET /api/student/assignments`
- `GET /api/student/courses`
- `GET /api/student/grades`

### Reports

Single endpoint with query param:

- `GET /api/reports?type=...`

Supported `type` values:

- `attendance`
- `task_completion`
- `teacher_subject_mapping`
- `course_statistics`
- `active_students`
- `graduated_students`
- `excellent_students`

Response shape:

- `type`, `title`, `generated_at`
- `columns: string[]`
- `rows: object[]`
- `summary: object`

## 6. Schedule overlap validation

On create/update schedule backend checks interval overlap by date for:

- same group, or
- same teacher

If overlap exists, backend returns `HTTP 400` with conflict details (discipline, group, teacher, time range).
Frontend shows this message via alert/toast.

## 7. Frontend modes

Configured in `frontend/config.js`:

- `DEMO_MODE=false`: real backend calls
- `DEMO_MODE=true`: mock dataset from `frontend/mockData.js`

Demo mode supports:

- login
- role-based dashboards
- assignment submit/lock/grade/reset simulation
- schedule create/update simulation
- report generation simulation for all 7 types

## 8. User pipelines (short)

### Student

1. Login/register
2. See all courses + my courses
3. Open assignments
4. Submit with mock file name
5. Wait for teacher grade or reset

### Teacher

1. Login
2. See grouped assignments by course
3. Review submissions
4. Set grade/status/feedback
5. Reset submission lock if needed
6. Use reports section

### Admin

1. Login
2. Create users/groups
3. Enroll students to groups
4. Manage schedule (with overlap validation)
5. Use reports section

## 9. Notes

- Profile privacy controls are removed; student profile is public by default.
- Logout in frontend clears auth and redirects directly to `/index.html`.
- Current report UI is intentionally simplified for defense demo.
- Telegram bot transport: in `BOT_MODE=auto`, if webhook setup fails, backend automatically falls back to polling mode.
- No additional webhook/polling input is required for this automatic fallback.
