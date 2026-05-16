"""
job_hunter/db.py
SQLite persistence layer — jobs, scholarships, tasks, profiles.
"""

import sqlite3, json, datetime, hashlib, secrets
from typing import List, Dict, Optional


# ════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ════════════════════════════════════════════════════════════════════════════
_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    record_type      TEXT DEFAULT 'job',
    title            TEXT,
    company          TEXT,
    location         TEXT,
    url              TEXT UNIQUE,
    source           TEXT,
    keyword          TEXT,
    sector           TEXT,
    deadline         TEXT,
    snippet          TEXT,
    full_description TEXT,
    cover_letter     TEXT,
    tailored_resume  TEXT,
    full_doc_md      TEXT,
    status           TEXT DEFAULT 'pending',
    match_score      INTEGER,
    user_id          TEXT DEFAULT 'default',
    scraped_at       TEXT,
    approved_at      TEXT,
    dispatched_at    TEXT
)"""

_SCHOLARSHIPS_DDL = """
CREATE TABLE IF NOT EXISTS scholarships (
    id                  TEXT PRIMARY KEY,
    record_type         TEXT DEFAULT 'scholarship',
    title               TEXT,
    funder              TEXT,
    company             TEXT,
    funder_country      TEXT,
    location            TEXT,
    region              TEXT,
    level               TEXT,
    field               TEXT,
    funding_type        TEXT,
    coverage            TEXT,
    eligible_countries  TEXT,
    url                 TEXT UNIQUE,
    source              TEXT,
    sector              TEXT DEFAULT 'scholarship',
    deadline            TEXT,
    snippet             TEXT,
    full_description    TEXT,
    motivation_letter   TEXT,
    research_proposal   TEXT,
    tailored_resume     TEXT,
    full_doc_md         TEXT,
    status              TEXT DEFAULT 'pending',
    match_score         INTEGER,
    user_id             TEXT DEFAULT 'default',
    scraped_at          TEXT,
    approved_at         TEXT,
    dispatched_at       TEXT
)"""

_TASKS_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    user_id     TEXT DEFAULT 'default',
    params_json TEXT,
    result_json TEXT,
    error       TEXT,
    created_at  TEXT,
    updated_at  TEXT
)"""

_PROFILES_DDL = """
CREATE TABLE IF NOT EXISTS profiles (
    user_id     TEXT PRIMARY KEY,
    api_key     TEXT UNIQUE,
    email       TEXT,
    data_json   TEXT,
    created_at  TEXT,
    updated_at  TEXT
)"""

_REPLIES_DDL = """
CREATE TABLE IF NOT EXISTS replies (
    id            TEXT PRIMARY KEY,
    record_id     TEXT NOT NULL,
    record_type   TEXT DEFAULT 'job',
    user_id       TEXT DEFAULT 'default',
    from_email    TEXT,
    from_name     TEXT,
    subject       TEXT,
    body_text     TEXT,
    received_at   TEXT,
    category      TEXT DEFAULT 'unknown',
    ai_draft      TEXT,
    is_read       INTEGER DEFAULT 0
)"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_jobs_status      ON jobs(status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_sector      ON jobs(sector)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_user        ON jobs(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_schol_status     ON scholarships(status)",
    "CREATE INDEX IF NOT EXISTS idx_schol_funding    ON scholarships(funding_type)",
    "CREATE INDEX IF NOT EXISTS idx_schol_country    ON scholarships(funder_country)",
    "CREATE INDEX IF NOT EXISTS idx_schol_region     ON scholarships(region)",
    "CREATE INDEX IF NOT EXISTS idx_schol_level      ON scholarships(level)",
    "CREATE INDEX IF NOT EXISTS idx_schol_user       ON scholarships(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_user       ON tasks(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_profiles_apikey  ON profiles(api_key)",
]

_MIGRATIONS = [
    "ALTER TABLE jobs        ADD COLUMN full_doc_md   TEXT",
    "ALTER TABLE jobs        ADD COLUMN record_type   TEXT DEFAULT 'job'",
    "ALTER TABLE jobs        ADD COLUMN user_id       TEXT DEFAULT 'default'",
    "ALTER TABLE scholarships ADD COLUMN user_id      TEXT DEFAULT 'default'",
]


# ════════════════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ════════════════════════════════════════════════════════════════════════════
class JobDB:
    def __init__(self, path: str = "jobs.db"):
        self.path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self):
        with self._conn() as c:
            c.execute(_JOBS_DDL)
            c.execute(_SCHOLARSHIPS_DDL)
            c.execute(_TASKS_DDL)
            c.execute(_PROFILES_DDL)
            c.execute(_REPLIES_DDL)
            for idx in _INDEXES:
                c.execute(idx)
            for m in _MIGRATIONS:
                try:
                    c.execute(m)
                except sqlite3.OperationalError:
                    pass

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _tbl(record_type: str) -> str:
        return "scholarships" if record_type == "scholarship" else "jobs"

    @staticmethod
    def _serialize(v):
        return json.dumps(v) if isinstance(v, (dict, list)) else v

    @staticmethod
    def _deserialize_row(row: sqlite3.Row) -> Dict:
        d = dict(row)
        for field in ("tailored_resume",):
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        return d

    @staticmethod
    def _now() -> str:
        return datetime.datetime.utcnow().isoformat()

    # ── WRITE — generic ──────────────────────────────────────────────────────
    def save(self, record: dict) -> bool:
        tbl    = self._tbl(record.get("record_type", "job"))
        fields = list(record.keys())
        vals   = [self._serialize(record[f]) for f in fields]
        ph     = ",".join(["?"] * len(fields))
        cols   = ",".join(fields)
        try:
            with self._conn() as c:
                c.execute(f"INSERT OR IGNORE INTO {tbl} ({cols}) VALUES ({ph})", vals)
                return c.rowcount > 0
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"DB save error [{tbl}]: {e}")
            return False

    def update(self, record_id: str, updates: dict,
               record_type: str = "job") -> bool:
        tbl  = self._tbl(record_type)
        sets = ", ".join([f"{k}=?" for k in updates])
        vals = [self._serialize(v) for v in updates.values()]
        vals.append(record_id)
        with self._conn() as c:
            c.execute(f"UPDATE {tbl} SET {sets} WHERE id=?", vals)
            return c.rowcount > 0

    def delete(self, record_id: str, record_type: str = "job") -> bool:
        tbl = self._tbl(record_type)
        with self._conn() as c:
            c.execute(f"DELETE FROM {tbl} WHERE id=?", (record_id,))
            return c.rowcount > 0

    # ── READ — jobs ──────────────────────────────────────────────────────────
    def exists(self, url: str, record_type: str = "job") -> bool:
        tbl = self._tbl(record_type)
        with self._conn() as c:
            row = c.execute(f"SELECT 1 FROM {tbl} WHERE url=?", (url,)).fetchone()
        return row is not None

    def get(self, record_id: str, record_type: str = "job") -> Optional[Dict]:
        tbl = self._tbl(record_type)
        with self._conn() as c:
            row = c.execute(f"SELECT * FROM {tbl} WHERE id=?", (record_id,)).fetchone()
        return self._deserialize_row(row) if row else None

    def get_by_status(self, status: str, record_type: str = "job",
                      user_id: str = "default",
                      page: int = 1, per_page: int = 50) -> List[Dict]:
        tbl    = self._tbl(record_type)
        offset = (page - 1) * per_page
        with self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM {tbl} WHERE status=? AND user_id=? "
                f"ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
                (status, user_id, per_page, offset)
            ).fetchall()
        return [self._deserialize_row(r) for r in rows]

    def get_all(self, record_type: str = "job", user_id: str = "default",
                limit: int = 500, offset: int = 0) -> List[Dict]:
        tbl = self._tbl(record_type)
        with self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM {tbl} WHERE user_id=? "
                f"ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset)
            ).fetchall()
        return [self._deserialize_row(r) for r in rows]

    def count_by_status(self, status: str, record_type: str = "job",
                        user_id: str = "default") -> int:
        tbl = self._tbl(record_type)
        with self._conn() as c:
            row = c.execute(
                f"SELECT COUNT(*) n FROM {tbl} WHERE status=? AND user_id=?",
                (status, user_id)
            ).fetchone()
        return row["n"] if row else 0

    # ── READ — scholarships ──────────────────────────────────────────────────
    def get_scholarships(
        self,
        status: Optional[str] = None,
        funding_type: Optional[str] = None,
        region: Optional[str] = None,
        funder_country: Optional[str] = None,
        level: Optional[str] = None,
        user_id: str = "default",
        page: int = 1,
        per_page: int = 50,
    ) -> List[Dict]:
        clauses, vals = ["user_id=?"], [user_id]
        if status:
            clauses.append("status=?"); vals.append(status)
        if funding_type:
            clauses.append("funding_type=?"); vals.append(funding_type)
        if region:
            clauses.append("region=?"); vals.append(region)
        if funder_country:
            clauses.append("funder_country LIKE ?"); vals.append(f"%{funder_country}%")
        if level:
            clauses.append("level LIKE ?"); vals.append(f"%{level}%")

        where  = "WHERE " + " AND ".join(clauses)
        offset = (page - 1) * per_page
        with self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM scholarships {where} "
                f"ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
                vals + [per_page, offset]
            ).fetchall()
        return [self._deserialize_row(r) for r in rows]

    def scholarship_exists(self, url: str) -> bool:
        return self.exists(url, "scholarship")

    def save_scholarship(self, s: dict) -> bool:
        s.setdefault("record_type", "scholarship")
        s.setdefault("company",  s.get("funder", ""))
        s.setdefault("location", s.get("funder_country", ""))
        return self.save(s)

    def update_scholarship(self, sid: str, updates: dict) -> bool:
        return self.update(sid, updates, "scholarship")

    # ── TASKS ────────────────────────────────────────────────────────────────
    def save_task(self, task: dict) -> bool:
        task.setdefault("created_at", self._now())
        task.setdefault("updated_at", self._now())
        fields = list(task.keys())
        vals   = [self._serialize(task[f]) for f in fields]
        ph     = ",".join(["?"] * len(fields))
        cols   = ",".join(fields)
        with self._conn() as c:
            c.execute(f"INSERT OR IGNORE INTO tasks ({cols}) VALUES ({ph})", vals)
            return c.rowcount > 0

    def update_task(self, task_id: str, updates: dict) -> bool:
        updates["updated_at"] = self._now()
        sets = ", ".join([f"{k}=?" for k in updates])
        vals = [self._serialize(v) for v in updates.values()]
        vals.append(task_id)
        with self._conn() as c:
            c.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals)
            return c.rowcount > 0

    def get_task(self, task_id: str) -> Optional[Dict]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for field in ("params_json", "result_json"):
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        return d

    def get_tasks(self, user_id: str = "default",
                  limit: int = 50) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM tasks WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── PROFILES ─────────────────────────────────────────────────────────────
    def save_profile(self, user_id: str, email: str,
                     data: dict, api_key: Optional[str] = None) -> str:
        existing = self.get_profile_by_user(user_id)
        key = api_key or (existing["api_key"] if existing else secrets.token_hex(32))
        now = self._now()
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO profiles "
                "(user_id, api_key, email, data_json, created_at, updated_at) "
                "VALUES (?,?,?,?,COALESCE((SELECT created_at FROM profiles WHERE user_id=?),?),?)",
                (user_id, key, email, json.dumps(data), user_id, now, now)
            )
        return key

    def get_profile_by_user(self, user_id: str) -> Optional[Dict]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM profiles WHERE user_id=?", (user_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("data_json"):
            try:
                d["data"] = json.loads(d["data_json"])
            except Exception:
                d["data"] = {}
        return d

    def get_profile_by_key(self, api_key: str) -> Optional[Dict]:
        hashed = hashlib.sha256(api_key.encode()).hexdigest()
        with self._conn() as c:
            # Try plaintext first (legacy), then hashed
            row = c.execute(
                "SELECT * FROM profiles WHERE api_key=? OR api_key=?",
                (api_key, hashed)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("data_json"):
            try:
                d["data"] = json.loads(d["data_json"])
            except Exception:
                d["data"] = {}
        return d

    # ── STATS ────────────────────────────────────────────────────────────────
    def stats(self, user_id: str = "default") -> Dict:
        result = {"jobs": {}, "scholarships": {}}
        with self._conn() as c:
            for row in c.execute(
                "SELECT status, COUNT(*) n FROM jobs WHERE user_id=? GROUP BY status",
                (user_id,)
            ):
                result["jobs"][row["status"]] = row["n"]
            for row in c.execute(
                "SELECT status, COUNT(*) n FROM scholarships WHERE user_id=? GROUP BY status",
                (user_id,)
            ):
                result["scholarships"][row["status"]] = row["n"]
            result["scholarships_by_funding"] = {}
            for row in c.execute(
                "SELECT funding_type, COUNT(*) n FROM scholarships "
                "WHERE user_id=? GROUP BY funding_type", (user_id,)
            ):
                result["scholarships_by_funding"][row["funding_type"] or "unknown"] = row["n"]
            result["scholarships_by_region"] = {}
            for row in c.execute(
                "SELECT region, COUNT(*) n FROM scholarships "
                "WHERE user_id=? GROUP BY region", (user_id,)
            ):
                result["scholarships_by_region"][row["region"] or "unknown"] = row["n"]
        return result

    def pipeline_summary(self, user_id: str = "default") -> Dict:
        s = self.stats(user_id)
        return {
            "jobs_pending":       s["jobs"].get("pending", 0),
            "jobs_ready":         s["jobs"].get("ready_for_review", 0),
            "jobs_approved":      s["jobs"].get("approved", 0),
            "jobs_dispatched":    s["jobs"].get("dispatched", 0),
            "schol_pending":      s["scholarships"].get("pending", 0),
            "schol_ready":        s["scholarships"].get("ready_for_review", 0),
            "schol_approved":     s["scholarships"].get("approved", 0),
            "schol_fully_funded": s["scholarships_by_funding"].get("fully_funded", 0),
            "schol_partial":      s["scholarships_by_funding"].get("partially_funded", 0),
        }

    # ── REPLIES ──────────────────────────────────────────────────────────────
    def save_reply(self, reply: dict) -> bool:
        reply.setdefault("id", secrets.token_hex(8))
        reply.setdefault("received_at", self._now())
        cols = ", ".join(reply.keys())
        placeholders = ", ".join("?" * len(reply))
        with self._conn() as c:
            c.execute(
                f"INSERT OR IGNORE INTO replies ({cols}) VALUES ({placeholders})",
                list(reply.values())
            )
        return True

    def get_replies(self, record_id: str, user_id: str = "default") -> List[Dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM replies WHERE record_id=? AND user_id=? ORDER BY received_at DESC",
                (record_id, user_id)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_reply_read(self, reply_id: str, user_id: str = "default") -> bool:
        with self._conn() as c:
            c.execute(
                "UPDATE replies SET is_read=1 WHERE id=? AND user_id=?",
                (reply_id, user_id)
            )
        return True

    def update_reply(self, reply_id: str, updates: dict) -> bool:
        sets = ", ".join(f"{k}=?" for k in updates)
        with self._conn() as c:
            c.execute(
                f"UPDATE replies SET {sets} WHERE id=?",
                list(updates.values()) + [reply_id]
            )
        return True

    def unread_reply_count(self, user_id: str = "default") -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) n FROM replies WHERE user_id=? AND is_read=0",
                (user_id,)
            ).fetchone()
        return row["n"] if row else 0

    # ── SEARCH ───────────────────────────────────────────────────────────────
    def search(self, query: str, record_type: str = "job",
               user_id: str = "default") -> List[Dict]:
        tbl = self._tbl(record_type)
        q   = f"%{query}%"
        with self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM {tbl} "
                f"WHERE user_id=? AND (title LIKE ? OR company LIKE ? OR snippet LIKE ?) "
                f"ORDER BY scraped_at DESC LIMIT 100",
                (user_id, q, q, q)
            ).fetchall()
        return [self._deserialize_row(r) for r in rows]

    # ── BULK / MAINTENANCE ───────────────────────────────────────────────────
    def bulk_save(self, records: List[dict]) -> int:
        saved = 0
        for r in records:
            if self.save(r):
                saved += 1
        return saved

    def purge_old(self, days: int = 90, status: str = "rejected",
                  record_type: str = "job") -> int:
        tbl    = self._tbl(record_type)
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
        with self._conn() as c:
            c.execute(
                f"DELETE FROM {tbl} WHERE status=? AND scraped_at<?",
                (status, cutoff)
            )
            return c.rowcount
