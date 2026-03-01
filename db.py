import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "votes.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS voters (
            voter_id    TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            photo_path  TEXT NOT NULL,
            has_voted   INTEGER DEFAULT 0
        );
    """)

    # Create anonymous votes table (no voter_id link)
    # If old schema exists with voter_id column, recreate it
    cursor = conn.execute("PRAGMA table_info(votes)")
    columns = [row[1] for row in cursor.fetchall()]
    if "voter_id" in columns:
        conn.executescript("""
            DROP TABLE IF EXISTS votes;
            CREATE TABLE votes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                party       TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            );
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                party       TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            );
        """)

    conn.commit()
    conn.close()


def get_voter_by_id(voter_id):
    conn = get_db_connection()
    voter = conn.execute(
        "SELECT * FROM voters WHERE voter_id = ?", (voter_id,)
    ).fetchone()
    conn.close()
    if voter:
        return dict(voter)
    return None


def get_all_unvoted_voters():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM voters WHERE has_voted = 0"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_voters():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM voters").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def record_vote(voter_id, party):
    conn = get_db_connection()
    try:
        voter = conn.execute(
            "SELECT has_voted FROM voters WHERE voter_id = ?", (voter_id,)
        ).fetchone()

        if voter is None:
            return False
        if voter["has_voted"] == 1:
            return False

        conn.execute(
            "INSERT INTO votes (party, timestamp) VALUES (?, ?)",
            (party, datetime.now().isoformat())
        )
        conn.execute(
            "UPDATE voters SET has_voted = 1 WHERE voter_id = ?",
            (voter_id,)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_vote_counts():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT party, COUNT(*) as count FROM votes GROUP BY party"
    ).fetchall()
    conn.close()
    return {row["party"]: row["count"] for row in rows}


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
