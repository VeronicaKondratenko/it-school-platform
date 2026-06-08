# Questions module style fix v5

Fixes standalone Questions pages that visually broke because they reused dashboard shell classes (`.app`, `.sidebar`, `.main`, `.section-card`, etc.) that were defined inline inside dashboard pages and were not available on `admin-questions.html`, `teacher-questions.html`, and `questions.html`.

Changed file:
- `frontend/questions-ui.css`

What was added:
- self-contained cabinet shell styles for sidebar, logo, navigation, main layout, cards, buttons, stats, and mobile toggle;
- light theme support;
- responsive behavior;
- strong logo image sizing to prevent the large logo issue.
