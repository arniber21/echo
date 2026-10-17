"""SQLite operations are short, transactional and use a connection per operation."""

import sqlite3
from pathlib import Path

from rewind.models import Case, Job


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.database = root / "rewind.sqlite3"
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS media_files (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, path TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL);
            """)
            rows = db.execute(
                "SELECT payload FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
            for (payload,) in rows:
                job = Job.model_validate_json(payload).model_copy(
                    update={
                        "status": "failed",
                        "stage": "failed",
                        "error": "Analysis was interrupted by a server restart. Retry analysis.",
                    }
                )
                db.execute(
                    "UPDATE jobs SET status=?, payload=? WHERE id=?",
                    (job.status, job.model_dump_json(), job.job_id),
                )

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def save_case(self, case: Case, paths: dict[str, Path] | None = None):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO cases VALUES (?, ?)",
                (case.case_id, case.model_dump_json()),
            )
            for source_id, path in (paths or {}).items():
                db.execute(
                    "INSERT OR REPLACE INTO media_files VALUES (?, ?, ?)",
                    (source_id, case.case_id, str(path)),
                )

    def get_case(self, case_id: str) -> Case | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM cases WHERE id=?", (case_id,)
            ).fetchone()
        return Case.model_validate_json(row[0]) if row else None

    def list_cases(self) -> list[Case]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM cases").fetchall()
        return sorted(
            (Case.model_validate_json(row[0]) for row in rows),
            key=lambda case: case.created_at,
            reverse=True,
        )

    def paths(self, case_id: str) -> dict[str, Path]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id, path FROM media_files WHERE case_id=?", (case_id,)
            ).fetchall()
        return {row[0]: Path(row[1]) for row in rows}

    def media(self, source_id: str):
        with self.connect() as db:
            row = db.execute(
                "SELECT case_id, path FROM media_files WHERE id=?", (source_id,)
            ).fetchone()
        if row:
            case = self.get_case(row[0])
            return next(
                (item for item in case.media_files if item.source_id == source_id), None
            ), Path(row[1])
        return None

    def save_job(self, job: Job):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?)",
                (job.job_id, job.case_id, job.status, job.model_dump_json()),
            )

    def get_job(self, job_id: str) -> Job | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        return Job.model_validate_json(row[0]) if row else None

    def active_job(self, case_id: str) -> Job | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM jobs WHERE case_id=? AND status IN ('queued','running')",
                (case_id,),
            ).fetchone()
        return Job.model_validate_json(row[0]) if row else None
