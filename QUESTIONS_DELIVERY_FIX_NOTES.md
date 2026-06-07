# Questions delivery fix

Fixed delivery and visibility of structured student questions:

- teacher inbox now also shows older/fallback teacher questions that were created without `target_user_id` but belong to one of the teacher's courses;
- teacher questions now also create an admin notification, so the admin receives an oversight notice for student-to-teacher questions;
- global navigation badges for unread notifications were restored in a non-floating, system-style way;
- opening student/teacher/admin question pages marks current notifications as read and refreshes the badge.

After deploying, test:
1. Student creates a question to admin → admin sees it in `admin-questions.html`.
2. Student creates a question to teacher → teacher sees it in `teacher-questions.html`; admin also sees it in `admin-questions.html`.
3. Teacher/admin replies → student sees reply in `questions.html`.
4. Navigation badge appears for unread notifications and disappears after opening the relevant page.
