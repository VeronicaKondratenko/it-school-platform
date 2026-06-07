# Telegram questions delivery fix

## What was wrong
Telegram bot questions to teacher/admin were saved into the legacy `messages` table.
The new web pages `admin-questions.html` and `teacher-questions.html` read the new structured module tables:

- `question_threads`
- `question_messages`
- `notifications`

So the bot confirmed that the question was sent, but admins/teachers did not see it in the web module.

## What changed
Updated `backend/app/bot/handlers.py`:

- Telegram questions to teacher/admin now create `QuestionThread` + `QuestionMessage` records.
- Teacher questions notify both the teacher and admins.
- Admin questions notify admins.
- Telegram AI questions are stored as `target_type='ai'`, so admins can see them in AI-запити.
- Teacher routing uses the student's group teacher and first course as context.
- If no teacher is assigned, the bot safely routes the question to admin instead of losing it.

## How to test
1. Deploy backend on Render.
2. Reconfigure Telegram webhook if needed.
3. In Telegram bot, press `Запитати`.
4. Choose `Викладач` or `Адмін`.
5. Send a test question.
6. Open web admin `Звернення` and teacher `Питання студентів`.
7. The question should be visible there.
