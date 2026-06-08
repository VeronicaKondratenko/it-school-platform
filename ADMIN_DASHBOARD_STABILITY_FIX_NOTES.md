# Admin dashboard stability fix

## What was fixed

1. Admin dashboard native sidebar is no longer overwritten by the global role-sidebar renderer.
   The global renderer is still used on shared pages, but `admin-dashboard.html` keeps its own button-based section navigation.

2. Sections opened by URL hash now work reliably:
   - `admin-dashboard.html#overview`
   - `admin-dashboard.html#users`
   - `admin-dashboard.html#courses`
   - `admin-dashboard.html#groups`
   - `admin-dashboard.html#schedule`
   - `admin-dashboard.html#reports`
   - `admin-dashboard.html#notifications`

3. Admin startup no longer freezes if one preload API request fails.
   Users/courses/groups are preloaded non-blockingly with `Promise.allSettled`.

4. Notifications section no longer stays on an infinite loader.
   It tries the legacy public notifications endpoint and falls back to the new notifications endpoint.

5. Inbox badge errors no longer break the dashboard.

## Files changed

- `frontend/api.js`
- `frontend/admin-dashboard.html`
