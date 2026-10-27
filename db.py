"""Tiny PostgreSQL helper used by the dashboard (psycopg 3)."""
import csv
import io
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import yaml

ROOT = Path(__file__).resolve().parent
# ISPINDEL_CONFIG points at another config file; ISPINDEL_DB_DSN overrides just the DSN
# (NFR-08: settings live in config.yml; inside the container network the DB is at `db`).
CFG = yaml.safe_load(Path(os.environ.get("ISPINDEL_CONFIG", ROOT / "config.yml")).read_text())
if os.environ.get("ISPINDEL_DB_DSN"):
    CFG["database"]["dsn"] = os.environ["ISPINDEL_DB_DSN"]
LOCAL = ZoneInfo(CFG["dashboard"]["timezone"])


def connect():
    """One short-lived connection per query - fine at this data volume."""
    return psycopg.connect(CFG["database"]["dsn"], autocommit=True)


def query(sql, params=None):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def execute(sql, params=None):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.rowcount


def local(ts):
    """UTC timestamp -> configured local time (NFR-09)."""
    return ts.astimezone(LOCAL)


def rows_to_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
