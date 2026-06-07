# Admin user save fix

Виправлено помилку збереження користувача в адмін-панелі, яка у браузері проявлялася як `Failed to fetch`.

Причина: backend повертав ORM-обʼєкт User після `commit/refresh`, а response_model намагався ліниво дочитати `groups` у async SQLAlchemy. Це могло давати 500/MissingGreenlet, який браузер показував як мережеву/CORS-помилку.

Виправлення:
- admin users endpoints повертають явний JSON-словник;
- users list/update перечитують групи з courses/students через selectinload;
- `StudyGroupBase.teacher_id` зроблено Optional, бо групи можуть бути без викладача;
- apiPut тепер показує зрозумілішу помилку при network/CORS failure.

Оновити Render потрібно для backend і frontend.
