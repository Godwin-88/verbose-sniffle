# Auth Bug — Post-Login 401 on /stats and /tasks

**Date:** 2026-05-16  
**Status:** Deferred — auth bypassed for feature testing. Revisit before multi-user/production deploy.

---

## Symptom

After a successful login (Supabase → `POST /profile/setup` → 200), all subsequent API calls
(`GET /stats`, `GET /tasks`, etc.) return **401 — Missing X-API-Key header**.

```
POST /profile/setup  → 200   ✓
GET  /stats          → 401   ✗
GET  /tasks          → 401   ✗
```

---

## Auth Flow (as designed)

1. User logs in via Supabase (`signInWithPassword` / magic link / Google OAuth).
2. `afterSupabaseLogin` runs:
   - Tries `GET /profile` (requires key → always 401 at this point).
   - Catch: calls `POST /profile/setup` → gets `{ api_key, user_id }`.
   - Calls `setAuth(api_key, user_id)` → stores key in Zustand.
3. `navigate('/')` → Dashboard loads → React Query fires `/stats`, `/tasks`.
4. `apiClient` request interceptor reads `useAuthStore.getState().apiKey` → attaches header.

---

## Root Cause Candidates Investigated

### Confirmed: `GET /profile` missing `api_key` in response
- `GET /profile` did not return `api_key` — only `user_id`, `email`, `profile`.
- **Fixed:** Added `"api_key": row.get("api_key")` to the response in `api_server.py:286`.
- This fixes the **returning user** path. Bug persists for new users (they go through `setupProfile`).

### Likely: Response interceptor `logout()` causing state corruption
- When `GET /profile` returns 401, the Axios response interceptor fires `logout()` immediately.
- `logout()` sets `apiKey = null` in Zustand.
- The catch block then calls `setupProfile()` (async — network round trip).
- `setAuth(key, userId)` is called AFTER the await.
- Something between `logout()` and the later `setAuth()` may be overwriting state back to null.
- Possible sub-causes:
  - Zustand `persist` middleware re-hydrating from localStorage (which has `null` from the `logout()` write) while `setupProfile()` is in-flight.
  - Supabase `onAuthStateChange` firing a `SIGNED_OUT` event between `logout()` and `setAuth()`.
  - React 18 concurrent rendering batching state in a way that discards the `setAuth` update.

### Attempted Fix 1: Always call `setupProfile` directly (skip `getProfile` attempt)
- `POST /profile/setup` is idempotent — returns existing key for known users, creates one for new.
- Eliminated the `getProfile()` 401 → `logout()` chain.
- **Result:** Bug persisted unchanged.

### Attempted Fix 2: `GET /profile` now returns `api_key`
- Helps returning users if the state issue is ever resolved.
- **Result:** Does not fix the new-user flow.

---

## Workaround (current)

Auth is bypassed for local dev/testing:

1. `VITE_API_KEY` added to `frontend/.env` — set to the `API_KEY` value from root `.env`.
2. `frontend/src/api/client.ts` — request interceptor falls back to `ENV_API_KEY` if Zustand has no key.
3. `frontend/src/App.tsx` — `ProtectedRoute` passes through if `ENV_API_KEY` is set.

The Flask backend still validates `X-API-Key` on every request via `require_auth`. The env key matches the master key checked first in `_resolve_user()`, so all requests are authorized as `user_id=default`.

---

## Files Changed

| File | Change |
|------|--------|
| `api_server.py:286` | `GET /profile` now returns `api_key` field |
| `frontend/src/pages/Setup.tsx` | Removed `getProfile()` try/catch; always calls `setupProfile()` |
| `frontend/src/api/client.ts` | Falls back to `VITE_API_KEY` env var in request interceptor |
| `frontend/src/App.tsx` | `ProtectedRoute` bypassed when `VITE_API_KEY` is set |
| `frontend/.env` | Added `VITE_API_KEY` |

---

## To Re-enable Auth Later

1. Remove `VITE_API_KEY` from `frontend/.env`.
2. Revert the `ENV_API_KEY` fallback in `client.ts` and `App.tsx`.
3. Properly debug Zustand state race — add `console.log` in `setAuth` and the request interceptor to confirm timing.
4. Consider: replace Zustand persist + interceptor pattern with a simpler approach — store the key in a module-level variable in `client.ts` and update it directly from `setAuth`.
