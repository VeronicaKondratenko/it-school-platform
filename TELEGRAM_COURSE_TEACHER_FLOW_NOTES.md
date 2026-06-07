# Telegram course → teacher question flow fix

## What changed

This patch fixes the ambiguous Telegram flow for student questions.

Before, when a student pressed **Запитати → Викладач**, the bot silently picked the first available teacher from the student's groups. This was confusing when the student studied several courses.

Now the flow is explicit:

1. Student presses **Запитати**.
2. Student chooses **Викладач**.
3. Bot shows course buttons.
4. Student chooses the course.
5. Bot shows teacher buttons for that course.
6. Student chooses a teacher.
7. Bot asks for the question text.
8. The question is created in `question_threads` with `course_id` and `target_user_id`.

The web student page now uses the same logic: first course, then teacher.

## Files changed

- `backend/app/bot/handlers.py`
- `backend/app/api/endpoints/questions.py`
- `frontend/questions.html`
- `frontend/questions-ui.css`

## Visual fixes

The patch also adds stronger contrast rules for questions pages so text in inputs, selects, textareas, dynamically inserted reply fields, and select options stays readable in light mode and dark mode.

## How to deploy

```bash
git add backend/app/bot/handlers.py backend/app/api/endpoints/questions.py frontend/questions.html frontend/questions-ui.css TELEGRAM_COURSE_TEACHER_FLOW_NOTES.md
git commit -m "Improve Telegram question flow and questions UI contrast"
git push
```

Then redeploy both services on Render:

- backend: Manual Deploy → Clear build cache & deploy
- frontend: Manual Deploy → Clear build cache & deploy

After deploy, open the site and press Ctrl+F5.
