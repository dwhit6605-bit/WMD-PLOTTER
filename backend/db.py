"""
SQLite-backed user store. No external database required.
Schema: users(id, username, password_hash, role, created_at, last_login)
"""

import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "users.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT    NOT NULL,
            role          TEXT    NOT NULL DEFAULT 'user',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            last_login    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tak_profiles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            host       TEXT    NOT NULL DEFAULT '',
            port       INTEGER NOT NULL DEFAULT 8089,
            marti_port INTEGER NOT NULL DEFAULT 8443,
            ssl        INTEGER NOT NULL DEFAULT 1,
            callsign   TEXT    NOT NULL DEFAULT 'WMD PLOTTER',
            cert_p12   TEXT,
            cert_pass  TEXT,
            is_active  INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    _migrate_tak_settings(conn)
    conn.close()


def _migrate_tak_settings(conn: sqlite3.Connection) -> None:
    """If no profiles exist yet but the old single-config settings are populated, import them."""
    count = conn.execute("SELECT COUNT(*) FROM tak_profiles").fetchone()[0]
    if count > 0:
        return
    host = conn.execute("SELECT value FROM settings WHERE key='tak_host'").fetchone()
    if not host or not host[0]:
        return
    host_val  = host[0]
    port_row  = conn.execute("SELECT value FROM settings WHERE key='tak_port'").fetchone()
    mport_row = conn.execute("SELECT value FROM settings WHERE key='tak_marti_port'").fetchone()
    ssl_row   = conn.execute("SELECT value FROM settings WHERE key='tak_ssl'").fetchone()
    cs_row    = conn.execute("SELECT value FROM settings WHERE key='tak_callsign'").fetchone()
    cert_row  = conn.execute("SELECT value FROM settings WHERE key='tak_cert_p12'").fetchone()
    cpass_row = conn.execute("SELECT value FROM settings WHERE key='tak_cert_pass'").fetchone()
    conn.execute(
        """INSERT INTO tak_profiles (name, host, port, marti_port, ssl, callsign, cert_p12, cert_pass, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            "Default",
            host_val,
            int(port_row[0]) if port_row and port_row[0] else 8089,
            int(mport_row[0]) if mport_row and mport_row[0] else 8443,
            1 if (ssl_row and ssl_row[0] == "true") else 0,
            cs_row[0] if cs_row and cs_row[0] else "WMD PLOTTER",
            cert_row[0] if cert_row else None,
            cpass_row[0] if cpass_row else None,
        ),
    )
    conn.commit()


def get_setting(key: str) -> Optional[str]:
    conn = _connect()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key: str, value: Optional[str]) -> None:
    conn = _connect()
    if value is None:
        conn.execute("DELETE FROM settings WHERE key=?", (key,))
    else:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
    conn.commit()
    conn.close()


def list_tak_profiles() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, host, port, marti_port, ssl, callsign, is_active, created_at,"
        " (cert_p12 IS NOT NULL) AS has_cert FROM tak_profiles ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tak_profile(profile_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM tak_profiles WHERE id=?", (profile_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_tak_profile() -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM tak_profiles WHERE is_active=1 ORDER BY id LIMIT 1"
    ).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM tak_profiles ORDER BY id LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_tak_profile(name: str, host: str, port: int, marti_port: int,
                       ssl: bool, callsign: str, profile_id: Optional[int] = None) -> int:
    conn = _connect()
    if profile_id:
        conn.execute(
            "UPDATE tak_profiles SET name=?, host=?, port=?, marti_port=?, ssl=?, callsign=? WHERE id=?",
            (name, host, port, marti_port, int(ssl), callsign, profile_id),
        )
        conn.commit()
        conn.close()
        return profile_id
    cur = conn.execute(
        "INSERT INTO tak_profiles (name, host, port, marti_port, ssl, callsign) VALUES (?,?,?,?,?,?)",
        (name, host, port, marti_port, int(ssl), callsign),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def set_tak_profile_cert(profile_id: int, cert_p12: Optional[str], cert_pass: Optional[str]) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE tak_profiles SET cert_p12=?, cert_pass=? WHERE id=?",
        (cert_p12, cert_pass, profile_id),
    )
    conn.commit()
    conn.close()


def set_active_tak_profile(profile_id: int) -> None:
    conn = _connect()
    conn.execute("UPDATE tak_profiles SET is_active=0")
    conn.execute("UPDATE tak_profiles SET is_active=1 WHERE id=?", (profile_id,))
    conn.commit()
    conn.close()


def delete_tak_profile(profile_id: int) -> bool:
    conn = _connect()
    cur = conn.execute("DELETE FROM tak_profiles WHERE id=?", (profile_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def count_users() -> int:
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return n


def get_user_by_username(username: str) -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(username: str, password_hash: str, role: str = "user") -> dict:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return {"id": user_id, "username": username, "role": role}


def update_last_login(user_id: int) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE users SET last_login = datetime('now') WHERE id = ?", (user_id,)
    )
    conn.commit()
    conn.close()


def list_users() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, username, role, created_at, last_login FROM users ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user(user_id: int) -> bool:
    conn = _connect()
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def update_password(user_id: int, password_hash: str) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
    )
    conn.commit()
    conn.close()
