# Fix: replies from web to Telegram + teacher UI cleanup

## What changed

1. `backend/app/api/endpoints/questions.py`
   - When a teacher/admin replies to a question in the web cabinet, the student now receives a Telegram message if their Telegram account is linked.
   - When a teacher/admin closes or redirects a question, the student also receives a Telegram message.
   - When a student уточнює питання and the teacher has Telegram linked, the teacher can receive a Telegram message too.
   - Telegram sending is non-blocking for the question workflow: if Telegram is not linked or temporarily fails, the web reply still saves correctly.

2. `frontend/teacher-dashboard.html`
   - Removed the confusing legacy `Повідомлення` menu item.
   - Old `#inbox` section now redirects users to the structured questions module.
   - Fixed a sidebar JavaScript bug where button-style menu items could break because the code expected every nav item to have `href`.

3. `frontend/teacher-questions.html`
   - Renamed the page to `Звернення студентів`.
   - Removed the legacy `Повідомлення` link from the sidebar.
   - Added a short explanation that this is the only working place for student questions.

## Conceptual difference after this patch

- `Звернення студентів` is the current working module for student questions, replies, statuses and notifications.
- The old `Повідомлення` section was a legacy inbox and is no longer recommended for teacher-student question flow.

## Deploy

```bash
git add backend/app/api/endpoints/questions.py frontend/teacher-dashboard.html frontend/teacher-questions.html REPLIES_AND_TEACHER_UI_FIX_NOTES.md
git commit -m "Fix question replies to Telegram and teacher questions UI"
git push
```

Then redeploy backend and frontend on Render.
