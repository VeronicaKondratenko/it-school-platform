# Role sidebar / profile consistency fix

## What was fixed

- Staff users (admin/teacher) now always see a stable role-specific sidebar on shared pages such as `profile.html`.
- The sidebar account block with avatar, name and role is injected consistently for admin/teacher pages where it was missing.
- Active menu highlighting is calculated by current page and hash, so items such as `Профіль`, `Звернення`, `Розклад`, `Курси`, `Звіти` and dashboard sections stay highlighted correctly.
- Dashboard hash navigation such as `admin-dashboard.html#courses` and `teacher-dashboard.html#assignments` is handled without switching to a student sidebar.
- Staff sidebars keep the same dark navy visual style in both dark and light themes.

## Files changed

- `frontend/api.js`

## Deployment

Update frontend on Render after pushing this file.
