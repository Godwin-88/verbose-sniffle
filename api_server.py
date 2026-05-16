"""
job_hunter/api_server.py

Production Flask API — authentication, rate limiting, background tasks,
email notifications, PDF export, multi-user profile management.

Auth: X-API-Key header (single-user: set API_KEY in .env)
Run:  python api_server.py   (port 5055)

────────────────────────────────────────────────────────────────────────────
ENDPOINTS
────────────────────────────────────────────────────────────────────────────
Auth
  POST /profile/setup          — first-time profile + API key setup
  GET  /profile                — get current user profile
  PUT  /profile                — update profile data

Tasks
  GET  /tasks                  — list recent background tasks
  GET  /tasks/<id>             — poll task status

Jobs
  POST /scrape                 — trigger scrape (async → task_id)
  POST /generate-docs          — generate AI docs (async → task_id)
  GET  /jobs                   — list jobs (status, page, per_page)
  GET  /jobs/<id>              — single job
  POST /jobs/<id>/approve      — approve + save edits → triggers review email
  POST /jobs/<id>/reject       — reject
  DELETE /jobs/<id>            — delete
  GET  /jobs/approved/pending-dispatch
  POST /jobs/<id>/mark-dispatched
  GET  /jobs/<id>/export       — download PDF / HTML package

Scholarships
  POST /scholarships/scrape          — async scrape
  POST /scholarships/generate-docs   — async AI docs
  GET  /scholarships                 — list (filters + pagination)
  GET  /scholarships/<id>
  POST /scholarships/<id>/approve
  POST /scholarships/<id>/reject
  DELETE /scholarships/<id>
  GET  /scholarships/approved/pending-dispatch
  POST /scholarships/<id>/mark-dispatched
  GET  /scholarships/<id>/export

Shared
  GET  /search                 — full-text search
  GET  /stats                  — pipeline stats
  GET  /health                 — health check (no auth)
  POST /webhooks/n8n           — n8n inbound webhook (HMAC-verified)
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json, os, uuid, datetime, logging, hashlib, hmac
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Optional

from flask import Flask, request, jsonify, Response, g
from flask_cors import CORS
from dotenv import load_dotenv

from db import JobDB
from scrapers import scrape_all, enrich_job_description
from scholarship_scrapers import scrape_scholarships
from ai_engine import generate_application_package, generate_scholarship_package, MODEL
from email_dispatch import notify_review_ready, notify_dispatched, notify_task_complete
from pdf_export import export_to_pdf, export_extension

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════
DB_PATH       = os.getenv("DB_PATH", "jobs.db")
API_KEY       = os.getenv("API_KEY", "")               # single-user master key
N8N_SECRET    = os.getenv("N8N_WEBHOOK_SECRET", "")    # HMAC secret for n8n webhooks
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
PROFILE_PATH  = os.path.join(os.path.dirname(__file__), "my_profile.json")
REVIEW_EMAIL  = os.getenv("REVIEW_RECIPIENT_EMAIL", "")

# ════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ════════════════════════════════════════════════════════════════════════════
app = Flask(__name__)

# CORS — restrict to configured origin in production
cors_origins = ALLOWED_ORIGIN if ALLOWED_ORIGIN != "*" else "*"
CORS(app, origins=cors_origins, allow_headers=["Content-Type", "X-API-Key"])

db       = JobDB(DB_PATH)
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jh-worker")


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _now() -> str:
    return datetime.datetime.utcnow().isoformat()

def _new_id() -> str:
    return str(uuid.uuid4())

def _load_profile_file() -> dict:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return {}

def _get_user_profile(user_id: str = "default") -> dict:
    row = db.get_profile_by_user(user_id)
    if row and row.get("data"):
        return row["data"]
    return _load_profile_file()

def _paginate(args) -> tuple[int, int]:
    try:
        page     = max(1, int(args.get("page", 1)))
        per_page = min(200, max(1, int(args.get("per_page", 50))))
    except (ValueError, TypeError):
        page, per_page = 1, 50
    return page, per_page

def _error(msg: str, code: int = 400) -> tuple:
    return jsonify({"error": msg}), code

def _ok(data: dict, code: int = 200) -> tuple:
    return jsonify(data), code


# ════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION MIDDLEWARE
# ════════════════════════════════════════════════════════════════════════════
def _resolve_user(key: str) -> Optional[dict]:
    """Return user profile dict if key is valid, else None."""
    # Master key from environment (single-user mode)
    if API_KEY and key == API_KEY:
        return {"user_id": "default", "email": REVIEW_EMAIL}
    # DB-backed key (multi-user)
    profile = db.get_profile_by_key(key)
    if profile:
        return {"user_id": profile["user_id"], "email": profile.get("email", "")}
    return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = (
            request.headers.get("X-API-Key")
            or request.args.get("api_key")
            or request.json.get("api_key") if request.is_json else None
        )
        if not key:
            return _error("Missing X-API-Key header", 401)
        user = _resolve_user(key)
        if not user:
            return _error("Invalid API key", 403)
        g.user_id = user["user_id"]
        g.user_email = user.get("email", REVIEW_EMAIL)
        return f(*args, **kwargs)
    return decorated


# ════════════════════════════════════════════════════════════════════════════
# RATE LIMITING (in-memory, per API key)
# ════════════════════════════════════════════════════════════════════════════
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    def _get_api_key():
        return request.headers.get("X-API-Key") or get_remote_address()

    limiter = Limiter(
        key_func=_get_api_key,
        app=app,
        default_limits=["200 per hour", "30 per minute"],
        storage_uri="memory://",
    )
    log.info("Rate limiting enabled (flask-limiter)")
except ImportError:
    log.warning("flask-limiter not installed — rate limiting disabled")
    class _NoLimiter:
        def limit(self, *a, **kw):
            return lambda f: f
        def exempt(self, f):
            return f
    limiter = _NoLimiter()


# ════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASK RUNNER
# ════════════════════════════════════════════════════════════════════════════
def _run_task(task_id: str, fn, *args, user_id: str = "default",
              user_email: str = ""):
    """Execute fn(*args) in background, update task table on completion."""
    db.update_task(task_id, {"status": "running"})
    try:
        result = fn(*args)
        db.update_task(task_id, {
            "status":      "done",
            "result_json": json.dumps(result),
        })
        task = db.get_task(task_id)
        if task:
            notify_task_complete(task, recipient=user_email or REVIEW_EMAIL)
    except Exception as e:
        log.exception(f"Task {task_id} failed")
        db.update_task(task_id, {"status": "failed", "error": str(e)})


def _submit_task(task_type: str, fn, *args,
                 params: dict = None, user_id: str = "default",
                 user_email: str = "") -> str:
    task_id = _new_id()
    db.save_task({
        "id":          task_id,
        "type":        task_type,
        "status":      "pending",
        "user_id":     user_id,
        "params_json": json.dumps(params or {}),
    })
    executor.submit(_run_task, task_id, fn, *args,
                    user_id=user_id, user_email=user_email)
    return task_id


# ════════════════════════════════════════════════════════════════════════════
# HEALTH (no auth)
# ════════════════════════════════════════════════════════════════════════════
@app.route("/health")
@limiter.exempt
def health():
    return jsonify({
        "status": "ok",
        "model":  MODEL,
        "db":     db.path,
        "stats":  db.pipeline_summary(),
    })


# ════════════════════════════════════════════════════════════════════════════
# PROFILE MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════
@app.route("/profile/setup", methods=["POST"])
@limiter.limit("10 per hour")
def profile_setup():
    """
    First-time setup: create a profile + generate an API key.
    No auth required (bootstrapping). If API_KEY env is set, that key is
    used instead and this endpoint validates it.
    Body: { "email": "...", "profile": {...}, "api_key": "optional override" }
    """
    payload    = request.json or {}
    email      = payload.get("email", "")
    profile    = payload.get("profile") or _load_profile_file()
    custom_key = payload.get("api_key")

    if not email:
        return _error("email is required")

    user_id = hashlib.sha256(email.encode()).hexdigest()[:16]
    key     = db.save_profile(user_id, email, profile, api_key=custom_key)
    log.info(f"Profile setup for {email} (user_id={user_id})")
    return jsonify({
        "user_id": user_id,
        "api_key": key,
        "message": "Profile created. Save your api_key — it will not be shown again.",
    })


@app.route("/profile", methods=["GET"])
@require_auth
def get_profile():
    row = db.get_profile_by_user(g.user_id)
    if not row:
        return _error("Profile not found. POST /profile/setup first.", 404)
    return jsonify({
        "user_id": row["user_id"],
        "email":   row["email"],
        "profile": row.get("data", {}),
        "api_key": row.get("api_key"),
    })


@app.route("/profile", methods=["PUT"])
@require_auth
def update_profile():
    payload = request.json or {}
    profile = payload.get("profile")
    if not profile:
        return _error("profile data required")
    row = db.get_profile_by_user(g.user_id)
    if not row:
        return _error("Profile not found. POST /profile/setup first.", 404)
    db.save_profile(g.user_id, row.get("email", ""), profile)
    return jsonify({"updated": True})


# ════════════════════════════════════════════════════════════════════════════
# TASKS
# ════════════════════════════════════════════════════════════════════════════
@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    tasks = db.get_tasks(user_id=g.user_id)
    return jsonify(tasks)


@app.route("/tasks/<task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    task = db.get_task(task_id)
    if not task:
        return _error("Task not found", 404)
    return jsonify(task)


# ════════════════════════════════════════════════════════════════════════════
# STATS
# ════════════════════════════════════════════════════════════════════════════
@app.route("/stats")
@require_auth
def stats():
    data = db.stats(user_id=g.user_id)
    data["unread_replies"] = db.unread_reply_count(g.user_id)
    return jsonify(data)


# ════════════════════════════════════════════════════════════════════════════
# REMINDERS
# ════════════════════════════════════════════════════════════════════════════
@app.route("/reminders/upcoming", methods=["GET"])
@require_auth
def reminders_upcoming():
    """
    Return items needing attention, grouped by urgency.
    Used by n8n to build and send the daily reminder digest.

    Query params:
      deadline_days  — items with deadline within N days (default 7)
      stale_hours    — approved-but-not-dispatched for > N hours (default 48)
    """
    deadline_days = int(request.args.get("deadline_days", 7))
    stale_hours   = int(request.args.get("stale_hours", 48))
    user_id       = g.user_id

    now       = datetime.datetime.utcnow()
    cutoff    = now + datetime.timedelta(days=deadline_days)
    stale_cut = now - datetime.timedelta(hours=stale_hours)

    def _days_left(deadline_str):
        try:
            d = datetime.datetime.strptime(deadline_str[:10], "%Y-%m-%d")
            return max(0, (d - now).days)
        except Exception:
            return None

    def _is_stale_approved(record):
        approved_at = record.get("approved_at") or record.get("updated_at") or ""
        try:
            t = datetime.datetime.fromisoformat(approved_at.replace("Z", "+00:00").replace("+00:00", ""))
            return t < stale_cut
        except Exception:
            return False

    expiring_jobs, expiring_schols, stale_jobs, stale_schols = [], [], [], []

    # Pull active jobs
    for status in ("pending", "ready_for_review", "approved"):
        for job in db.get_all("job", user_id=user_id, limit=500):
            if job.get("status") != status:
                continue
            dl = job.get("deadline", "")
            if dl:
                try:
                    d = datetime.datetime.strptime(dl[:10], "%Y-%m-%d")
                    if now <= d <= cutoff:
                        job["days_left"] = _days_left(dl)
                        expiring_jobs.append(job)
                except Exception:
                    pass
            if status == "approved" and _is_stale_approved(job):
                stale_jobs.append(job)

    # Pull active scholarships
    for status in ("pending", "ready_for_review", "approved"):
        for schol in db.get_scholarships(status=status, user_id=user_id, per_page=500):
            dl = schol.get("deadline", "")
            if dl:
                try:
                    d = datetime.datetime.strptime(dl[:10], "%Y-%m-%d")
                    if now <= d <= cutoff:
                        schol["days_left"] = _days_left(dl)
                        expiring_schols.append(schol)
                except Exception:
                    pass
            if status == "approved" and _is_stale_approved(schol):
                stale_schols.append(schol)

    # Deduplicate by id
    def _dedup(lst):
        seen, out = set(), []
        for item in lst:
            if item["id"] not in seen:
                seen.add(item["id"]); out.append(item)
        return out

    result = {
        "expiring_jobs":          _dedup(sorted(expiring_jobs,  key=lambda x: x.get("days_left") or 999)),
        "expiring_scholarships":  _dedup(sorted(expiring_schols, key=lambda x: x.get("days_left") or 999)),
        "stale_approved_jobs":    _dedup(stale_jobs),
        "stale_approved_schols":  _dedup(stale_schols),
        "summary": {
            "expiring_jobs":         len(_dedup(expiring_jobs)),
            "expiring_scholarships": len(_dedup(expiring_schols)),
            "stale_jobs":            len(_dedup(stale_jobs)),
            "stale_schols":          len(_dedup(stale_schols)),
        },
        "generated_at": now.isoformat() + "Z",
    }
    return jsonify(result)


@app.route("/reminders/send-digest", methods=["POST"])
@require_auth
def reminders_send_digest():
    """
    Trigger the digest email immediately (manual send or called by n8n).
    Body (all optional):
      { "deadline_days": 7, "stale_hours": 48, "recipient": "override@email.com" }
    """
    from email_dispatch import notify_reminder_digest

    body          = request.json or {}
    deadline_days = int(body.get("deadline_days", 7))
    stale_hours   = int(body.get("stale_hours", 48))
    recipient     = body.get("recipient") or g.user_email

    # Reuse the logic from /reminders/upcoming
    now       = datetime.datetime.utcnow()
    cutoff    = now + datetime.timedelta(days=deadline_days)
    stale_cut = now - datetime.timedelta(hours=stale_hours)
    user_id   = g.user_id

    def _days_left(dl):
        try:
            return max(0, (datetime.datetime.strptime(dl[:10], "%Y-%m-%d") - now).days)
        except Exception:
            return None

    def _stale(rec):
        t_str = rec.get("approved_at") or rec.get("updated_at") or ""
        try:
            t = datetime.datetime.fromisoformat(t_str.replace("Z",""))
            return t < stale_cut
        except Exception:
            return False

    expiring_jobs, expiring_schols, stale_jobs, stale_schols = [], [], [], []
    for job in db.get_all("job", user_id=user_id, limit=500):
        if job.get("status") in ("pending", "ready_for_review", "approved"):
            dl = job.get("deadline", "")
            if dl:
                try:
                    d = datetime.datetime.strptime(dl[:10], "%Y-%m-%d")
                    if now <= d <= cutoff:
                        job["days_left"] = _days_left(dl); expiring_jobs.append(job)
                except Exception: pass
            if job.get("status") == "approved" and _stale(job):
                stale_jobs.append(job)
    for schol in db.get_scholarships(user_id=user_id, per_page=500):
        if schol.get("status") in ("pending", "ready_for_review", "approved"):
            dl = schol.get("deadline", "")
            if dl:
                try:
                    d = datetime.datetime.strptime(dl[:10], "%Y-%m-%d")
                    if now <= d <= cutoff:
                        schol["days_left"] = _days_left(dl); expiring_schols.append(schol)
                except Exception: pass
            if schol.get("status") == "approved" and _stale(schol):
                stale_schols.append(schol)

    sent = notify_reminder_digest(
        expiring_jobs=expiring_jobs,
        expiring_schols=expiring_schols,
        stale_jobs=stale_jobs,
        stale_schols=stale_schols,
        recipient=recipient,
        deadline_days=deadline_days,
    )
    return jsonify({"sent": sent, "recipient": recipient})


# ════════════════════════════════════════════════════════════════════════════
# ── JOB ENDPOINTS ────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def _do_scrape_jobs(keywords, sources, user_id):
    jobs  = scrape_all(keywords, sources)
    saved = 0
    for job in jobs:
        if not db.exists(job.get("url", ""), "job"):
            job["id"]          = _new_id()
            job["status"]      = "pending"
            job["record_type"] = "job"
            job["user_id"]     = user_id
            job["scraped_at"]  = _now()
            if db.save(job):
                saved += 1
    log.info(f"[scrape_jobs] scraped={len(jobs)} new={saved}")
    return {"scraped": len(jobs), "new": saved, "sources": sources}


def _do_generate_job_docs(job_ids, profile, user_id, max_jobs):
    if job_ids:
        pending = [db.get(jid, "job") for jid in job_ids]
    else:
        pending = db.get_by_status("pending", "job", user_id=user_id,
                                   per_page=max_jobs)
    pending = [j for j in pending if j][:max_jobs]
    results = []
    for job in pending:
        try:
            pkg = generate_application_package(job, profile)
            db.update(job["id"], {
                "cover_letter":    pkg["cover_letter_md"],
                "tailored_resume": pkg["tailored_resume"],
                "full_doc_md":     pkg["full_doc_md"],
                "match_score":     pkg["match_score"],
                "status":          "ready_for_review",
            }, "job")
            # Auto-notify if email configured
            updated_job = db.get(job["id"], "job")
            if updated_job:
                notify_review_ready(updated_job, "job")
            results.append({"id": job["id"], "title": job["title"],
                            "match_score": pkg["match_score"], "ok": True})
        except Exception as e:
            log.error(f"generate-docs job {job.get('id')}: {e}")
            results.append({"id": job.get("id"), "error": str(e)})
    return {"processed": len(results), "results": results}


@app.route("/scrape", methods=["POST"])
@require_auth
@limiter.limit("10 per hour")
def scrape_jobs():
    payload  = request.json or {}
    profile  = _get_user_profile(g.user_id)
    keywords = payload.get("keywords", profile.get("target_roles",
               ["data analyst", "software engineer"]))
    sources  = payload.get("sources", [
        "neaims", "gaa", "brightermonday", "myjobmag",
        "fuzu", "jobwebkenya", "careersinkenya",
        "ngojobskenya", "linkedin", "reddit",
    ])
    task_id = _submit_task(
        "scrape_jobs",
        _do_scrape_jobs,
        keywords, sources, g.user_id,
        params={"keywords": keywords, "sources": sources},
        user_id=g.user_id,
        user_email=g.user_email,
    )
    return jsonify({"task_id": task_id, "status": "running",
                    "poll": f"/tasks/{task_id}"})


@app.route("/generate-docs", methods=["POST"])
@require_auth
@limiter.limit("20 per hour")
def generate_job_docs():
    payload  = request.json or {}
    profile  = payload.get("profile") or _get_user_profile(g.user_id)
    job_id   = payload.get("job_id")
    max_jobs = int(payload.get("max", 20))

    task_id = _submit_task(
        "generate_job_docs",
        _do_generate_job_docs,
        [job_id] if job_id else [], profile, g.user_id, max_jobs,
        params={"job_id": job_id, "max": max_jobs},
        user_id=g.user_id,
        user_email=g.user_email,
    )
    return jsonify({"task_id": task_id, "status": "running",
                    "poll": f"/tasks/{task_id}"})


@app.route("/jobs", methods=["GET"])
@require_auth
def list_jobs():
    status    = request.args.get("status", "ready_for_review")
    sector    = request.args.get("sector")
    page, pp  = _paginate(request.args)
    jobs      = db.get_by_status(status, "job", user_id=g.user_id,
                                  page=page, per_page=pp)
    if sector:
        jobs = [j for j in jobs if j.get("sector") == sector]
    total = db.count_by_status(status, "job", user_id=g.user_id)
    return jsonify({"data": jobs, "page": page, "per_page": pp, "total": total})


@app.route("/jobs/<job_id>", methods=["GET"])
@require_auth
def get_job(job_id):
    job = db.get(job_id, "job")
    if not job:
        return _error("Not found", 404)
    return jsonify(job)


@app.route("/jobs/<job_id>/approve", methods=["POST"])
@require_auth
def approve_job(job_id):
    payload = request.json or {}
    db.update(job_id, {
        "status":          "approved",
        "cover_letter":    payload.get("cover_letter"),
        "full_doc_md":     payload.get("full_doc_md"),
        "tailored_resume": payload.get("tailored_resume"),
        "approved_at":     _now(),
    }, "job")
    return jsonify({"status": "approved"})


@app.route("/jobs/<job_id>/reject", methods=["POST"])
@require_auth
def reject_job(job_id):
    db.update(job_id, {"status": "rejected"}, "job")
    return jsonify({"status": "rejected"})


@app.route("/jobs/<job_id>", methods=["DELETE"])
@require_auth
def delete_job(job_id):
    ok = db.delete(job_id, "job")
    return jsonify({"deleted": ok})


@app.route("/jobs/approved/pending-dispatch", methods=["GET"])
@require_auth
def jobs_pending_dispatch():
    page, pp = _paginate(request.args)
    jobs = db.get_by_status("approved", "job", user_id=g.user_id,
                             page=page, per_page=pp)
    return jsonify({"data": jobs})


@app.route("/jobs/<job_id>/mark-dispatched", methods=["POST"])
@require_auth
def mark_job_dispatched(job_id):
    db.update(job_id, {"status": "dispatched", "dispatched_at": _now()}, "job")
    job = db.get(job_id, "job")
    if job:
        notify_dispatched(job, "job", recipient=g.user_email)
    return jsonify({"status": "dispatched"})


@app.route("/jobs/<job_id>/export", methods=["GET"])
@require_auth
def export_job(job_id):
    job = db.get(job_id, "job")
    if not job:
        return _error("Not found", 404)
    md    = job.get("full_doc_md") or job.get("cover_letter") or "No document generated yet."
    title = f"{job.get('title','Job')} @ {job.get('company','')}"
    data, mime = export_to_pdf(md, title)
    ext = export_extension()
    return Response(
        data,
        mimetype=mime,
        headers={"Content-Disposition":
                 f'attachment; filename="application_{job_id[:8]}.{ext}"'},
    )


# ════════════════════════════════════════════════════════════════════════════
# ── SCHOLARSHIP ENDPOINTS ─────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════
def _do_scrape_scholarships(keywords, sources, region_filter, funding_filter, user_id):
    scholarships = scrape_scholarships(
        keywords=keywords, sources=sources,
        region_filter=region_filter, funding_filter=funding_filter,
    )
    saved = 0
    for s in scholarships:
        if not db.scholarship_exists(s.get("url", "")):
            s["id"]         = _new_id()
            s["status"]     = "pending"
            s["user_id"]    = user_id
            s["scraped_at"] = _now()
            if db.save_scholarship(s):
                saved += 1
    log.info(f"[scrape_scholarships] scraped={len(scholarships)} new={saved}")
    return {"scraped": len(scholarships), "new": saved}


def _do_generate_scholarship_docs(schol_ids, profile, user_id, max_docs):
    if schol_ids:
        pending = [db.get(sid, "scholarship") for sid in schol_ids]
    else:
        pending = db.get_scholarships(status="pending", user_id=user_id,
                                      per_page=max_docs)
    pending = [s for s in pending if s][:max_docs]
    results = []
    for s in pending:
        try:
            pkg = generate_scholarship_package(s, profile)
            db.update_scholarship(s["id"], {
                "motivation_letter": pkg["motivation_letter"],
                "research_proposal": pkg["research_proposal"],
                "tailored_resume":   pkg["tailored_resume"],
                "full_doc_md":       pkg["full_doc_md"],
                "match_score":       pkg["match_score"],
                "status":            "ready_for_review",
            })
            updated = db.get(s["id"], "scholarship")
            if updated:
                notify_review_ready(updated, "scholarship")
            results.append({"id": s["id"], "title": s["title"],
                            "match_score": pkg["match_score"], "ok": True})
        except Exception as e:
            log.error(f"generate scholarship docs {s.get('id')}: {e}")
            results.append({"id": s.get("id"), "error": str(e)})
    return {"processed": len(results), "results": results}


@app.route("/scholarships/scrape", methods=["POST"])
@require_auth
@limiter.limit("10 per hour")
def scrape_scholarships_route():
    payload        = request.json or {}
    profile        = _get_user_profile(g.user_id)
    keywords       = payload.get("keywords",
                       profile.get("target_roles", ["development"]) +
                       profile.get("target_sectors", []))
    sources        = payload.get("sources")
    region_filter  = payload.get("region_filter")
    funding_filter = payload.get("funding_filter")

    task_id = _submit_task(
        "scrape_scholarships",
        _do_scrape_scholarships,
        keywords, sources, region_filter, funding_filter, g.user_id,
        params=payload,
        user_id=g.user_id,
        user_email=g.user_email,
    )
    return jsonify({"task_id": task_id, "status": "running",
                    "poll": f"/tasks/{task_id}"})


@app.route("/scholarships/generate-docs", methods=["POST"])
@require_auth
@limiter.limit("20 per hour")
def generate_scholarship_docs():
    payload  = request.json or {}
    profile  = payload.get("profile") or _get_user_profile(g.user_id)
    schol_id = payload.get("scholarship_id")
    max_docs = int(payload.get("max", 10))

    task_id = _submit_task(
        "generate_scholarship_docs",
        _do_generate_scholarship_docs,
        [schol_id] if schol_id else [], profile, g.user_id, max_docs,
        params={"scholarship_id": schol_id, "max": max_docs},
        user_id=g.user_id,
        user_email=g.user_email,
    )
    return jsonify({"task_id": task_id, "status": "running",
                    "poll": f"/tasks/{task_id}"})


@app.route("/scholarships", methods=["GET"])
@require_auth
def list_scholarships():
    page, pp = _paginate(request.args)
    scholarships = db.get_scholarships(
        status         = request.args.get("status", "ready_for_review"),
        funding_type   = request.args.get("funding_type"),
        region         = request.args.get("region"),
        funder_country = request.args.get("funder_country"),
        level          = request.args.get("level"),
        user_id        = g.user_id,
        page=page, per_page=pp,
    )
    return jsonify({"data": scholarships, "page": page, "per_page": pp})


@app.route("/scholarships/<schol_id>", methods=["GET"])
@require_auth
def get_scholarship(schol_id):
    s = db.get(schol_id, "scholarship")
    if not s:
        return _error("Not found", 404)
    return jsonify(s)


@app.route("/scholarships/<schol_id>/approve", methods=["POST"])
@require_auth
def approve_scholarship(schol_id):
    payload = request.json or {}
    db.update_scholarship(schol_id, {
        "status":             "approved",
        "motivation_letter":  payload.get("motivation_letter"),
        "full_doc_md":        payload.get("full_doc_md"),
        "tailored_resume":    payload.get("tailored_resume"),
        "research_proposal":  payload.get("research_proposal"),
        "approved_at":        _now(),
    })
    return jsonify({"status": "approved"})


@app.route("/scholarships/<schol_id>/reject", methods=["POST"])
@require_auth
def reject_scholarship(schol_id):
    db.update_scholarship(schol_id, {"status": "rejected"})
    return jsonify({"status": "rejected"})


@app.route("/scholarships/<schol_id>", methods=["DELETE"])
@require_auth
def delete_scholarship(schol_id):
    ok = db.delete(schol_id, "scholarship")
    return jsonify({"deleted": ok})


@app.route("/scholarships/approved/pending-dispatch", methods=["GET"])
@require_auth
def scholarships_pending_dispatch():
    page, pp = _paginate(request.args)
    schols = db.get_scholarships(status="approved", user_id=g.user_id,
                                  page=page, per_page=pp)
    return jsonify({"data": schols})


@app.route("/scholarships/<schol_id>/mark-dispatched", methods=["POST"])
@require_auth
def mark_scholarship_dispatched(schol_id):
    db.update_scholarship(schol_id, {
        "status": "dispatched", "dispatched_at": _now()
    })
    s = db.get(schol_id, "scholarship")
    if s:
        notify_dispatched(s, "scholarship", recipient=g.user_email)
    return jsonify({"status": "dispatched"})


@app.route("/scholarships/<schol_id>/export", methods=["GET"])
@require_auth
def export_scholarship(schol_id):
    s = db.get(schol_id, "scholarship")
    if not s:
        return _error("Not found", 404)
    md    = s.get("full_doc_md") or s.get("motivation_letter") or "No document generated yet."
    title = f"{s.get('title','Scholarship')} — Application Package"
    data, mime = export_to_pdf(md, title)
    ext = export_extension()
    return Response(
        data,
        mimetype=mime,
        headers={"Content-Disposition":
                 f'attachment; filename="scholarship_{schol_id[:8]}.{ext}"'},
    )


# ════════════════════════════════════════════════════════════════════════════
# SEARCH
# ════════════════════════════════════════════════════════════════════════════
@app.route("/search", methods=["GET"])
@require_auth
def search():
    q    = request.args.get("q", "")
    rtype = request.args.get("type", "job")
    if not q:
        return jsonify([])
    return jsonify(db.search(q, rtype, user_id=g.user_id))


# ════════════════════════════════════════════════════════════════════════════
# EMAIL REPLIES
# ════════════════════════════════════════════════════════════════════════════
REPLY_CATEGORIES = {
    "interview_invite": ["interview", "schedule", "meet", "call", "shortlisted", "invite", "assessment"],
    "rejection":        ["unfortunately", "regret", "not successful", "not moving forward", "other candidates", "not selected"],
    "info_request":     ["could you", "please provide", "send us", "attach", "more information", "clarification"],
    "offer":            ["pleased to offer", "job offer", "offer letter", "offer of employment"],
    "acknowledgement":  ["received your application", "thank you for applying", "we will review"],
}

def _classify_reply(subject: str, body: str) -> str:
    text = (subject + " " + body).lower()
    for category, keywords in REPLY_CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return category
    return "unknown"

def _find_record_by_company(company: str, user_id: str) -> Optional[dict]:
    """Best-effort match: find an approved/dispatched job by company name in email."""
    if not company:
        return None
    results = db.search(company, "job", user_id=user_id)
    for r in results:
        if r.get("status") in ("approved", "dispatched", "ready_for_review"):
            return r
    return None


@app.route("/replies", methods=["GET"])
@require_auth
def list_all_replies():
    """List all replies for the user, most recent first. Used for an inbox view."""
    limit = int(request.args.get("limit", 50))
    unread_only = request.args.get("unread") == "1"
    with db._conn() as c:
        q = "SELECT * FROM replies WHERE user_id=?"
        params = [g.user_id]
        if unread_only:
            q += " AND is_read=0"
        q += " ORDER BY received_at DESC LIMIT ?"
        params.append(limit)
        rows = c.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/replies/unread-count", methods=["GET"])
@require_auth
def replies_unread_count():
    return jsonify({"count": db.unread_reply_count(g.user_id)})


@app.route("/jobs/<job_id>/replies", methods=["GET"])
@require_auth
def get_job_replies(job_id):
    return jsonify(db.get_replies(job_id, g.user_id))


@app.route("/jobs/<job_id>/replies", methods=["POST"])
@require_auth
def add_job_reply(job_id):
    """
    Store an inbound email reply. Called by n8n after Gmail trigger.
    Body: { from_email, from_name, subject, body_text, received_at? }
    """
    body = request.json or {}
    subject   = body.get("subject", "")
    body_text = body.get("body_text", "")
    category  = _classify_reply(subject, body_text)

    reply = {
        "record_id":   job_id,
        "record_type": "job",
        "user_id":     g.user_id,
        "from_email":  body.get("from_email", ""),
        "from_name":   body.get("from_name", ""),
        "subject":     subject,
        "body_text":   body_text,
        "received_at": body.get("received_at") or _now(),
        "category":    category,
        "is_read":     0,
    }
    db.save_reply(reply)
    return jsonify({"status": "saved", "category": category}), 201


@app.route("/replies/inbound", methods=["POST"])
def replies_inbound():
    """
    Public webhook called by n8n Gmail trigger (no user auth — uses api_key in body).
    n8n sends: { api_key, from_email, from_name, subject, body_text, received_at }
    We match the job automatically by searching company name extracted from email sender domain.
    """
    if N8N_SECRET:
        sig      = request.headers.get("X-N8N-Signature", "")
        raw_body = request.get_data()
        expected = hmac.new(N8N_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return _error("Invalid signature", 403)

    payload   = request.json or {}
    api_key   = payload.get("api_key", "")
    user      = _resolve_user(api_key) if api_key else None
    user_id   = user["user_id"] if user else "default"

    subject    = payload.get("subject", "")
    body_text  = payload.get("body_text", "")
    from_email = payload.get("from_email", "")
    from_name  = payload.get("from_name", "")
    record_id  = payload.get("record_id")   # n8n can pass this explicitly if known
    category   = _classify_reply(subject, body_text)

    # Auto-match to a job if record_id not provided
    if not record_id:
        domain  = from_email.split("@")[-1].split(".")[0] if "@" in from_email else ""
        matched = _find_record_by_company(domain or from_name, user_id)
        record_id = matched["id"] if matched else None

    if not record_id:
        return jsonify({"status": "unmatched", "category": category}), 200

    # Generate AI draft reply
    ai_draft = None
    try:
        job = db.get(record_id, "job")
        if job:
            from ai_engine import client, MODEL
            prompt = f"""You are helping a job applicant reply to an employer email.

Job applied for: {job.get('title')} at {job.get('company')}
Email category: {category}
Email from: {from_name} <{from_email}>
Subject: {subject}
Body:
{body_text[:1500]}

Write a professional, concise reply (3–5 sentences). Match the tone of the email.
Do not add placeholders — write a ready-to-send reply."""
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            ai_draft = resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning(f"AI draft failed: {e}")

    reply = {
        "record_id":   record_id,
        "record_type": "job",
        "user_id":     user_id,
        "from_email":  from_email,
        "from_name":   from_name,
        "subject":     subject,
        "body_text":   body_text,
        "received_at": payload.get("received_at") or _now(),
        "category":    category,
        "ai_draft":    ai_draft,
        "is_read":     0,
    }
    db.save_reply(reply)
    return jsonify({"status": "saved", "category": category, "record_id": record_id}), 201


@app.route("/replies/<reply_id>/read", methods=["POST"])
@require_auth
def mark_reply_read(reply_id):
    db.mark_reply_read(reply_id, g.user_id)
    return jsonify({"status": "ok"})


# ════════════════════════════════════════════════════════════════════════════
# N8N WEBHOOK INBOUND (n8n → API)
# ════════════════════════════════════════════════════════════════════════════
@app.route("/webhooks/n8n", methods=["POST"])
def n8n_webhook():
    """
    n8n calls this endpoint to trigger actions (e.g., after email reply approval).
    Secured by HMAC-SHA256 signature in X-N8N-Signature header if N8N_WEBHOOK_SECRET set.
    Body: { "action": "approve|reject|dispatch", "id": "...", "type": "job|scholarship" }
    """
    if N8N_SECRET:
        sig  = request.headers.get("X-N8N-Signature", "")
        body = request.get_data()
        expected = hmac.new(N8N_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return _error("Invalid webhook signature", 403)

    payload = request.json or {}
    action  = payload.get("action")
    rec_id  = payload.get("id")
    rtype   = payload.get("type", "job")

    if not action or not rec_id:
        return _error("action and id required")

    if action == "approve":
        if rtype == "scholarship":
            db.update_scholarship(rec_id, {"status": "approved", "approved_at": _now()})
        else:
            db.update(rec_id, {"status": "approved", "approved_at": _now()}, "job")
        return jsonify({"status": "approved", "id": rec_id})

    if action == "reject":
        if rtype == "scholarship":
            db.update_scholarship(rec_id, {"status": "rejected"})
        else:
            db.update(rec_id, {"status": "rejected"}, "job")
        return jsonify({"status": "rejected", "id": rec_id})

    if action == "dispatch":
        if rtype == "scholarship":
            db.update_scholarship(rec_id, {"status": "dispatched", "dispatched_at": _now()})
            rec = db.get(rec_id, "scholarship")
        else:
            db.update(rec_id, {"status": "dispatched", "dispatched_at": _now()}, "job")
            rec = db.get(rec_id, "job")
        if rec:
            notify_dispatched(rec, rtype)
        return jsonify({"status": "dispatched", "id": rec_id})

    return _error(f"Unknown action: {action}")


# ════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ════════════════════════════════════════════════════════════════════════════
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Rate limit exceeded. Slow down."}), 429

@app.errorhandler(500)
def internal_error(e):
    log.exception("Unhandled 500")
    return jsonify({"error": "Internal server error"}), 500


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not API_KEY:
        log.warning(
            "⚠️  API_KEY not set in .env — ALL requests will be REJECTED. "
            "Set API_KEY or use POST /profile/setup to create a user."
        )
    log.info(f"Job Hunter KE API — model: {MODEL}")
    log.info(f"Database: {db.path}")
    log.info(f"Stats: {db.pipeline_summary()}")
    app.run(host="0.0.0.0", port=5055, debug=False, use_reloader=False)
