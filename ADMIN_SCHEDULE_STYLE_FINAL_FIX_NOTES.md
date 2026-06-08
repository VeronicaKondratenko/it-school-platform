# Admin schedule and light UI final fix

## What was fixed

- The admin dashboard now has a role-scoped light-theme block inside `admin-dashboard.html`.
- Admin sections such as Overview, Users, Courses, Groups, Schedule, Reports and Notifications now use the same light surfaces, table colors, text colors and button contrast.
- The Schedule section is no longer visually different from the rest of the admin dashboard in light mode.
- The fix is scoped to `body.admin-dashboard-page`, so it does not alter student or teacher pages.

## Files changed

- `frontend/admin-dashboard.html`

## Deployment

Deploy the frontend service after pushing this change.
