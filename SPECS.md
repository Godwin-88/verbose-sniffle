# Job Hunter KE — Frontend UI Specification
**Version:** 1.0  
**Stack:** React 18 + TypeScript + Tailwind CSS + shadcn/ui  
**API Base:** `http://localhost:5055` (env: `VITE_API_BASE_URL`)  
**Auth:** `X-API-Key` header on every request

---

## 1. Design Principles

- **Minimal, functional** — every pixel earns its place. No decorative elements.
- **Data-dense but readable** — tables over cards where possible. Cards only for document previews.
- **Single-page, no full reloads** — React Query for data fetching + optimistic UI.
- **Mobile-aware** — sidebar collapses to bottom nav on < 768px.
- **Status-driven color system** — consistent pill colors across all record types.

### Status Color Map
| Status | Color |
|--------|-------|
| `pending` | Gray |
| `ready_for_review` | Amber |
| `approved` | Blue |
| `dispatched` | Green |
| `rejected` | Red |
| `running` (task) | Indigo (pulse) |
| `done` (task) | Green |
| `failed` (task) | Red |

---

## 2. Layout

```
┌──────────────────────────────────────────────────────────────┐
│  TOPBAR  [Logo]  [Search bar]              [User] [Settings] │
├──────────┬───────────────────────────────────────────────────┤
│          │                                                    │
│ SIDEBAR  │                 MAIN CONTENT                      │
│  (220px) │                                                    │
│          │                                                    │
└──────────┴───────────────────────────────────────────────────┘
```

### Sidebar Navigation Items
```
  ◉  Dashboard          /
  ─────────────────
  💼  Jobs              /jobs
  🎓  Scholarships      /scholarships
  ─────────────────
  ⚡  Tasks             /tasks
  ─────────────────
  👤  Profile           /profile
  ⚙️  Settings          /settings
```

Each nav item shows a **badge count** for `ready_for_review` items (jobs + scholarships).

---

## 3. Pages

---

### 3.1  Dashboard  `/`

**Purpose:** At-a-glance pipeline health. First screen after login.

**Layout:** Stats row → two columns (Jobs pipeline | Scholarships pipeline) → Recent activity feed.

#### Stats Bar (6 cards, full width)
| Metric | Source |
|--------|--------|
| Jobs Pending | `stats.jobs.pending` |
| Jobs Ready for Review | `stats.jobs.ready_for_review` |
| Jobs Approved | `stats.jobs.approved` |
| Scholarships Ready | `stats.scholarships.ready_for_review` |
| Fully Funded Scholarships | `stats.scholarships_by_funding.fully_funded` |
| Dispatched (total) | `jobs.dispatched + scholarships.dispatched` |

Each card: large number, label, subtle trend icon (up/down vs. last session — stored in localStorage).

#### Pipeline Funnel (two side-by-side)
Horizontal bar showing: `pending → ready → approved → dispatched → rejected`  
Proportional fill. Click any segment to navigate to that filtered list.

#### Quick Actions (button row)
- **Scrape Jobs** → `POST /scrape` (fires async, shows task toast)
- **Scrape Scholarships** → `POST /scholarships/scrape`
- **Generate AI Docs** → `POST /generate-docs` (runs on all pending)
- **Generate Scholarship Docs** → `POST /scholarships/generate-docs`

All quick-action buttons show a spinner and disable while a task of that type is `running`. Poll `GET /tasks` every 5s when any task is running; stop polling when all done.

#### Recent Tasks Feed
Last 10 tasks from `GET /tasks`. Columns: Type · Status · Started · Duration. Live-updating.

---

### 3.2  Jobs  `/jobs`

#### Sub-navigation tabs (filter by status)
`All` · `Pending` · `Ready for Review` · `Approved` · `Dispatched` · `Rejected`

Each tab shows count badge.

#### Toolbar
- **Search** input (debounced 300ms → `GET /search?q=&type=job`)
- **Sector** dropdown filter
- **Sort** by: Date scraped · Match score · Deadline
- **Scrape Now** button (top-right) → triggers async scrape task

#### Jobs Table
| Column | Notes |
|--------|-------|
| Title | Clickable → opens Job Detail slide-over |
| Company | — |
| Location | — |
| Deadline | Red text if < 3 days away |
| Source | Chip (e.g. BrighterMonday) |
| Match | Progress bar + `XX%` |
| Status | Colored pill |
| Actions | `Review` · `·` overflow menu |

Pagination: `Previous / Next` with `per_page` selector (20 / 50 / 100).

#### Job Detail — Slide-over Panel (right side, 600px)

Opens on row click. Does NOT navigate away.

```
┌─────────────────────────────────────────────────────┐
│ [← Back]  Senior Data Analyst @ KRA      [✕ Close] │
│  BrighterMonday · Nairobi · Deadline: 20 Jun 2026   │
│  Match: ████████░░  82%                             │
├─────────────────────────────────────────────────────┤
│  TABS: Cover Letter │ Resume Insights │ Full Package │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [Editable markdown/text area]                      │
│                                                     │
├─────────────────────────────────────────────────────┤
│  [✓ Approve & Save]  [✗ Reject]  [⬇ Export PDF]   │
└─────────────────────────────────────────────────────┘
```

**Tab: Cover Letter**  
- Rendered Markdown preview (toggle: Preview / Edit)
- Edit mode: `<textarea>` pre-filled with `cover_letter`
- Changes saved on Approve

**Tab: Resume Insights**  
- Match score badge
- `highlighted_skills` → chip list
- `keywords` → chip list (ATS keywords)
- `bullet_rewrites` → two-column table (Original → Rewritten)
- `summary` → text block

**Tab: Full Package**  
- Full rendered Markdown of `full_doc_md`
- Read-only

**Actions:**
- **Approve & Save** → `POST /jobs/<id>/approve` with any edits → status pill updates → slide-over closes → row updates in table
- **Reject** → `POST /jobs/<id>/reject` → confirm dialog → row moves to Rejected tab
- **Export PDF** → `GET /jobs/<id>/export` → triggers file download
- **Overflow menu** → Delete (`DELETE /jobs/<id>`)

---

### 3.3  Scholarships  `/scholarships`

Identical structure to Jobs with these differences:

#### Additional Filters (toolbar)
- **Funding Type**: All · Fully Funded · Partially Funded
- **Region**: All · Africa · Europe · Asia · Americas · Global
- **Level**: All · Masters · PhD · Undergraduate · Short Course
- **Funder Country**: text search

#### Scholarships Table
| Column | Notes |
|--------|-------|
| Title | Clickable → slide-over |
| Funder | — |
| Country | Flag emoji + country name |
| Level | Chip |
| Funding | `Fully Funded` (green) / `Partial` (amber) |
| Deadline | Red if < 7 days |
| Match | Progress bar |
| Status | Pill |
| Actions | — |

#### Scholarship Detail — Slide-over Panel

```
TABS: Motivation Letter │ CV Tailoring │ Research Proposal │ Full Package
```

**Tab: Motivation Letter** — editable, same as cover letter pattern.

**Tab: CV Tailoring**  
- `strengths` list
- `gaps` list (what to address)
- Selection criteria alignment table
- `bullet_rewrites` table

**Tab: Research Proposal** (only shown if `level === 'phd'`)  
- Rendered Markdown, editable

**Tab: Full Package** — read-only rendered doc.

**Actions:** Approve & Save · Reject · Export PDF · Delete

---

### 3.4  Tasks  `/tasks`

**Purpose:** Visibility into all background jobs (scraping, AI generation).

#### Tasks Table
| Column | Notes |
|--------|-------|
| Type | `scrape_jobs` / `generate_job_docs` / `scrape_scholarships` / `generate_scholarship_docs` |
| Status | Animated pill — `running` pulses |
| Started | Relative time (e.g. "2 min ago") |
| Duration | `updated_at - created_at` if done |
| Result | e.g. "Scraped 24 · New 8" parsed from `result_json` |
| Error | Red text if `failed` |

Auto-refreshes every 5s when any task is `pending` or `running`. Stops when all terminal.

**Empty state:** "No tasks yet. Use the Quick Actions on the Dashboard to start."

---

### 3.5  Profile  `/profile`

**Purpose:** Manage the candidate profile that the AI uses to generate all documents.

#### Layout: Two columns

**Left: Profile Form**

Sections (accordion):
1. **Personal Info** — name, email, phone, location, LinkedIn
2. **Target Preferences** — target_roles (tag input), target_sectors (tag input), work_preferences (checkboxes: remote/hybrid/onsite), locations_ok (tag input), min_salary_ksh (number input)
3. **Summary** — textarea (professional summary)
4. **Education** — repeatable rows: degree, institution, year, grade. Add/remove buttons.
5. **Experience** — repeatable rows: title, company, dates, bullets (textarea). Add/remove.
6. **Skills** — technical (tag input), soft (tag input), languages (tag input)
7. **Certifications** — repeatable: name. Add/remove.
8. **Notable Achievements** — repeatable: text. Add/remove.
9. **Referees** — repeatable: name, title, email, phone.

**Save button** → `PUT /profile` with full profile JSON.

**Right: Profile Completeness Score**

```
Profile Strength ████████░░  80%

✓ Personal info complete
✓ 2 work experiences
✓ Education added
⚠ No certifications
⚠ Summary is short (< 50 words)
```

Checklist auto-computed from form state. Not persisted.

**Danger Zone** (bottom, collapsed by default):  
- Regenerate API Key (shows new key once in modal)

---

### 3.6  Settings  `/settings`

Minimal. Two sections:

**Scraping Defaults**
- Default keywords (tag input) — pre-filled from profile target_roles
- Default sources (multi-select checkboxes): BrighterMonday, Fuzu, LinkedIn, GAA, NEAIMS, MyJobMag, JobWebKenya, CareersInKenya, NGOJobsKenya, Reddit
- Default scholarship region filter (select)
- Default scholarship funding filter (select)

These settings are stored in `localStorage` and sent as request body to `/scrape` and `/scholarships/scrape`.

**Notifications**
- Review email address (shown from profile, link to `/profile` to change)
- Email provider indicator (SMTP / SendGrid — read from `GET /health`, display only)

No save button needed — changes persist to localStorage on blur.

---

## 4. Global Components

### 4.1  Search Bar (Topbar)
- Debounced input, 300ms
- Calls `GET /search?q=<term>&type=job` and `GET /search?q=<term>&type=scholarship` in parallel
- Dropdown results: split by type, max 5 each
- Click result → opens detail slide-over on correct page

### 4.2  Task Toast System
When a quick-action button is pressed:
```
┌──────────────────────────────────────────────┐
│  ⚡ Scraping jobs...              [View Tasks]│
│  Task ID: abc123 · Started 2s ago            │
└──────────────────────────────────────────────┘
```
Toast updates in place: `running → done ("Scraped 24, 8 new")` or `failed ("Error: ...")`.  
Auto-dismisses 5s after completion.

### 4.3  Confirm Dialog
Used for: Reject, Delete.  
Minimal: title + description + `Cancel` / `Confirm (destructive)` buttons.

### 4.4  Export Download Handler
`GET /<type>/<id>/export` triggers a fetch with auth header → creates object URL → programmatic `<a>` click → revoke URL. Shows loading state on the button.

---

## 5. Authentication Flow

### Onboarding (unauthenticated state)
Route: `/setup` (shown when no `api_key` in localStorage)

```
┌────────────────────────────────┐
│       Job Hunter KE            │
│                                │
│  Email ___________________     │
│                                │
│  [ Load my_profile.json ]  or  │
│  [ Paste JSON profile ]        │
│                                │
│  [ Create Account & API Key ]  │
│                                │
│  Already have a key?           │
│  API Key _________________ [→] │
└────────────────────────────────┘
```

On submit → `POST /profile/setup` → save `api_key` to localStorage → redirect to `/`.

### Persistent Auth
- API key stored in `localStorage` key `jh_api_key`
- Attached as `X-API-Key` header in a central Axios/fetch instance
- On 401/403 → clear localStorage → redirect to `/setup`

---

## 6. API → UI Mapping (complete)

| API Endpoint | Used In |
|---|---|
| `GET /health` | Settings page (provider info), background connectivity check |
| `GET /stats` | Dashboard stats bar + funnel |
| `POST /profile/setup` | Onboarding `/setup` |
| `GET /profile` | Profile page (load), topbar user display |
| `PUT /profile` | Profile page (save) |
| `GET /tasks` | Dashboard feed, Tasks page |
| `GET /tasks/<id>` | Toast polling after quick actions |
| `POST /scrape` | Dashboard quick action, Jobs toolbar |
| `POST /generate-docs` | Dashboard quick action |
| `GET /jobs?status=&page=&per_page=` | Jobs page table |
| `GET /jobs/<id>` | Job detail slide-over |
| `POST /jobs/<id>/approve` | Slide-over approve button |
| `POST /jobs/<id>/reject` | Slide-over reject button |
| `DELETE /jobs/<id>` | Slide-over overflow menu |
| `GET /jobs/approved/pending-dispatch` | Jobs "Approved" tab |
| `POST /jobs/<id>/mark-dispatched` | Jobs approved tab action |
| `GET /jobs/<id>/export` | Slide-over export button |
| `POST /scholarships/scrape` | Dashboard quick action, Scholarships toolbar |
| `POST /scholarships/generate-docs` | Dashboard quick action |
| `GET /scholarships?status=&funding_type=&region=&level=&page=` | Scholarships page table |
| `GET /scholarships/<id>` | Scholarship detail slide-over |
| `POST /scholarships/<id>/approve` | Slide-over approve button |
| `POST /scholarships/<id>/reject` | Slide-over reject button |
| `DELETE /scholarships/<id>` | Slide-over overflow menu |
| `GET /scholarships/approved/pending-dispatch` | Scholarships "Approved" tab |
| `POST /scholarships/<id>/mark-dispatched` | Approved tab action |
| `GET /scholarships/<id>/export` | Slide-over export button |
| `GET /search?q=&type=` | Global topbar search |

---

## 7. Tech Stack Recommendations

| Concern | Choice | Reason |
|---|---|---|
| Framework | React 18 + TypeScript | Type safety, ecosystem |
| Build | Vite | Fast dev + build |
| UI Components | shadcn/ui + Tailwind | Minimal, composable, no bloat |
| Data Fetching | TanStack Query (React Query) | Caching, polling, optimistic updates |
| HTTP Client | Axios | Interceptors for auth header |
| Routing | React Router v6 | Standard |
| Markdown Render | react-markdown + remark-gfm | Clean GFM rendering |
| Markdown Edit | @uiw/react-md-editor | Split preview/edit |
| Forms | React Hook Form | Performant, minimal re-renders |
| Icons | lucide-react | Ships with shadcn |
| Relative Time | date-fns | `formatDistanceToNow` |
| State (global) | Zustand | Auth key, toast queue |

---

## 8. File Structure

```
src/
├── api/
│   ├── client.ts          # axios instance with X-API-Key interceptor
│   ├── jobs.ts            # job API functions
│   ├── scholarships.ts    # scholarship API functions
│   ├── tasks.ts
│   ├── profile.ts
│   └── stats.ts
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── Topbar.tsx
│   │   └── AppShell.tsx
│   ├── shared/
│   │   ├── StatusPill.tsx      # consistent status badge
│   │   ├── MatchBar.tsx        # progress bar for match score
│   │   ├── ConfirmDialog.tsx
│   │   ├── TaskToast.tsx
│   │   └── ExportButton.tsx
│   ├── jobs/
│   │   ├── JobsTable.tsx
│   │   └── JobDetailPanel.tsx
│   └── scholarships/
│       ├── ScholarshipsTable.tsx
│       └── ScholarshipDetailPanel.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── Jobs.tsx
│   ├── Scholarships.tsx
│   ├── Tasks.tsx
│   ├── Profile.tsx
│   ├── Settings.tsx
│   └── Setup.tsx           # onboarding
├── hooks/
│   ├── useTasks.ts         # polling logic
│   ├── useQuickAction.ts   # fire async task + show toast
│   └── useExport.ts        # fetch + trigger download
├── store/
│   └── auth.ts             # Zustand: api_key, user_id
└── main.tsx
```

---

## 9. SaaS Extensibility Notes

These are not in scope for v1 but the UI should not block them:

- **Multi-user:** `/profile/setup` already returns `user_id`. When adding Stripe billing, wrap routes in a `<PlanGate>` component checking a `plan` field on the profile response.
- **White-labeling:** Logo and primary color pulled from a `/config` endpoint (not yet implemented in API) or env vars — structure Tailwind theme tokens accordingly.
- **Onboarding wizard:** Replace the current single-step `/setup` page with a 3-step wizard (Email → Upload Profile JSON → API Key reveal) without changing routing.
- **Bulk actions:** Table rows have checkboxes stubbed out (disabled in v1). Wire to bulk approve/reject endpoints when added to API.
