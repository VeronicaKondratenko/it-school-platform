# Патч: модуль “Питання / Звернення”

Додано структурований модуль для питань студентів до адміністратора, викладача та журналу AI-запитів.

## Змінені/додані файли

Backend:
- `backend/app/models.py` — додано таблиці `question_threads`, `question_messages`, `notifications`.
- `backend/app/schemas.py` — додано схеми питань, повідомлень і сповіщень.
- `backend/app/api/endpoints/questions.py` — нові API для створення, перегляду, відповіді, закриття та перенаправлення питань.
- `backend/app/api/endpoints/notifications.py` — API для сповіщень.
- `backend/app/api/endpoints/chat.py` — AI-запити студентів зберігаються в журналі питань.
- `backend/app/main.py` — підключено нові routers.

Frontend:
- `frontend/questions.html` — сторінка студента “Питання”.
- `frontend/teacher-questions.html` — сторінка викладача “Питання студентів”.
- `frontend/admin-questions.html` — сторінка адміністратора “Звернення та AI-запити”.
- `frontend/api.js` — додано API helpers, PATCH-запити, глобальний індикатор сповіщень.
- Оновлено sidebar-посилання у студентських сторінках, `teacher-dashboard.html`, `admin-dashboard.html`.

## Як оновити Render

1. Скопіювати файли патча у локальний проєкт із заміною.
2. Виконати:

```bash
git add .
git commit -m "Add questions appeals module with notifications"
git push
```

3. На Render зробити redeploy backend і frontend.
4. Переконатися, що для backend є `AUTO_CREATE_DB=true`, щоб нові таблиці створилися автоматично.
5. Перевірити:
   - студент: `questions.html`;
   - викладач: `teacher-questions.html`;
   - адміністратор: `admin-questions.html`.

## Перевірено

- Python compile: OK.
- JavaScript syntax: OK.
- Нові сторінки використовують стилі системи і не змінюють існуючі базові сторінки критично.
