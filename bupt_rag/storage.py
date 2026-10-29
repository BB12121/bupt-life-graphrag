import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


class Store:
    """SQLite is authoritative. A single transaction publishes a ready snapshot."""

    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "knowledge.sqlite3"
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS snapshots (
                revision INTEGER PRIMARY KEY, commit_sha TEXT NOT NULL,
                config_key TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS vectors (
                model TEXT NOT NULL, content_hash TEXT NOT NULL, vector TEXT NOT NULL,
                PRIMARY KEY (model, content_hash));
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS extractions (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def latest(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM snapshots ORDER BY revision DESC LIMIT 1").fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    def extraction_record(self, key):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM extractions WHERE id=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def extraction_records(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM extractions ORDER BY id")]

    def save_extraction(self, record):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO extractions VALUES (?,?)",
                (record["id"], json.dumps(record, ensure_ascii=False)),
            )

    def historical_document(self, doc_id, commit):
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM snapshots WHERE commit_sha=? ORDER BY revision DESC", (commit,)
            )
            for row in rows:
                for doc in json.loads(row[0])["documents"].values():
                    if doc["document"]["id"] == doc_id:
                        return doc
        return None

    def cached_vectors(self, model):
        with self.connect() as db:
            return {
                row[0]: json.loads(row[1])
                for row in db.execute("SELECT content_hash, vector FROM vectors WHERE model=?", (model,))
            }

    def publish(self, commit, config_key, payload, model, vectors):
        created = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            revision = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM snapshots").fetchone()[0]
            db.executemany(
                "INSERT OR IGNORE INTO vectors VALUES (?,?,?)",
                [(model, key, json.dumps(value)) for key, value in vectors.items()],
            )
            db.execute(
                "INSERT INTO snapshots VALUES (?,?,?,?,?)",
                (revision, commit, config_key, created, json.dumps(payload, ensure_ascii=False)),
            )
        return {
            "revision": revision,
            "commit_sha": commit,
            "config_key": config_key,
            "created_at": created,
            "payload": payload,
        }
