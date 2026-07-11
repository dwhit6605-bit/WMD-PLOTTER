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
        CREATE TABLE IF NOT EXISTS scenarios (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            name          TEXT    NOT NULL,
            tool          TEXT    NOT NULL,
            lat           REAL    NOT NULL DEFAULT 0.0,
            lon           REAL    NOT NULL DEFAULT 0.0,
            state_json    TEXT    NOT NULL DEFAULT '{}',
            response_json TEXT    NOT NULL DEFAULT '{}',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scenarios_user ON scenarios(user_id, created_at DESC)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tak_profiles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            host             TEXT    NOT NULL DEFAULT '',
            port             INTEGER NOT NULL DEFAULT 8089,
            marti_port       INTEGER NOT NULL DEFAULT 8443,
            ssl              INTEGER NOT NULL DEFAULT 1,
            callsign         TEXT    NOT NULL DEFAULT 'WMD PLOTTER',
            cert_p12         TEXT,
            cert_pass        TEXT,
            truststore_p12   TEXT,
            truststore_pass  TEXT,
            is_active        INTEGER NOT NULL DEFAULT 0,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    # Add truststore columns to existing databases (idempotent); also rename
    # admin_cert_* → truststore_* if the old column names exist.
    for old, new, typedef in [
        ("admin_cert_p12",  "truststore_p12",  "TEXT"),
        ("admin_cert_pass", "truststore_pass", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE tak_profiles RENAME COLUMN {old} TO {new}")
        except Exception:
            pass
        try:
            conn.execute(f"ALTER TABLE tak_profiles ADD COLUMN {new} {typedef}")
        except Exception:
            pass  # column already exists
    # Incidents
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            name          TEXT    NOT NULL DEFAULT 'Untitled Incident',
            ics_number    TEXT,
            incident_type TEXT    NOT NULL DEFAULT 'HazMat',
            status        TEXT    NOT NULL DEFAULT 'active',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_user ON incidents(user_id, created_at DESC)")

    # Facility presets (org-wide, admin-managed)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS facilities (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL,
            facility_type       TEXT    NOT NULL DEFAULT 'industrial',
            lat                 REAL    NOT NULL,
            lon                 REAL    NOT NULL,
            chemical_id         TEXT,
            default_rate_kg_min REAL,
            release_height_m    REAL    NOT NULL DEFAULT 0.0,
            notes               TEXT,
            created_by          INTEGER,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Organizations
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Idempotent migrations
    for col, typedef in [
        ("incident_id", "INTEGER"),
        ("org_id",      "INTEGER"),
    ]:
        try:
            conn.execute(f"ALTER TABLE scenarios ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN org_id INTEGER")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE tak_profiles ADD COLUMN org_id INTEGER")
    except Exception:
        pass

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


def list_tak_profiles(org_id: Optional[int] = None, org_scoped: bool = False) -> list:
    conn = _connect()
    if org_scoped:
        # Return only profiles belonging to this org (or global if org_id is None)
        rows = conn.execute(
            "SELECT id, name, host, port, marti_port, ssl, callsign, is_active, created_at, org_id,"
            " (cert_p12 IS NOT NULL) AS has_cert,"
            " (truststore_p12 IS NOT NULL) AS has_truststore"
            " FROM tak_profiles WHERE org_id IS ? ORDER BY id",
            (org_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, host, port, marti_port, ssl, callsign, is_active, created_at, org_id,"
            " (cert_p12 IS NOT NULL) AS has_cert,"
            " (truststore_p12 IS NOT NULL) AS has_truststore"
            " FROM tak_profiles ORDER BY id"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tak_profile(profile_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM tak_profiles WHERE id=?", (profile_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_tak_profile(org_id: Optional[int] = None) -> Optional[dict]:
    conn = _connect()
    # Try org-specific active profile first
    if org_id is not None:
        row = conn.execute(
            "SELECT * FROM tak_profiles WHERE org_id=? AND is_active=1 LIMIT 1", (org_id,)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM tak_profiles WHERE org_id=? ORDER BY id LIMIT 1", (org_id,)
            ).fetchone()
        if row:
            conn.close()
            return dict(row)
    # Fall back to global (org_id IS NULL)
    row = conn.execute(
        "SELECT * FROM tak_profiles WHERE org_id IS NULL AND is_active=1 LIMIT 1"
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM tak_profiles WHERE org_id IS NULL ORDER BY id LIMIT 1"
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_tak_profile(name: str, host: str, port: int, marti_port: int,
                       ssl: bool, callsign: str, profile_id: Optional[int] = None,
                       org_id: Optional[int] = None) -> int:
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
        "INSERT INTO tak_profiles (name, host, port, marti_port, ssl, callsign, org_id) VALUES (?,?,?,?,?,?,?)",
        (name, host, port, marti_port, int(ssl), callsign, org_id),
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


def set_tak_profile_truststore(profile_id: int, truststore_p12: Optional[str], truststore_pass: Optional[str]) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE tak_profiles SET truststore_p12=?, truststore_pass=? WHERE id=?",
        (truststore_p12, truststore_pass, profile_id),
    )
    conn.commit()
    conn.close()


def set_active_tak_profile(profile_id: int) -> None:
    conn = _connect()
    # Only deactivate profiles in the same org scope as the one being activated
    row = conn.execute("SELECT org_id FROM tak_profiles WHERE id=?", (profile_id,)).fetchone()
    org_id = row["org_id"] if row else None
    if org_id is None:
        conn.execute("UPDATE tak_profiles SET is_active=0 WHERE org_id IS NULL")
    else:
        conn.execute("UPDATE tak_profiles SET is_active=0 WHERE org_id=?", (org_id,))
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
        """SELECT u.id, u.username, u.role, u.created_at, u.last_login,
                  u.org_id, o.name AS org_name
           FROM users u
           LEFT JOIN organizations o ON o.id = u.org_id
           ORDER BY u.created_at"""
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


def set_user_role(user_id: int, role: str) -> bool:
    conn = _connect()
    cur = conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def set_user_org(user_id: int, org_id: Optional[int]) -> bool:
    conn = _connect()
    cur = conn.execute(
        "UPDATE users SET org_id = ? WHERE id = ?", (org_id, user_id)
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


# ── Organizations ─────────────────────────────────────────────────────────────

def list_orgs() -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT o.id, o.name, o.created_at,
                  COUNT(u.id) AS member_count
           FROM organizations o
           LEFT JOIN users u ON u.org_id = o.id
           GROUP BY o.id ORDER BY o.name COLLATE NOCASE"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_org(name: str) -> dict:
    conn = _connect()
    cur = conn.execute("INSERT INTO organizations (name) VALUES (?)", (name,))
    conn.commit()
    row = conn.execute("SELECT * FROM organizations WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


def update_org(org_id: int, name: str) -> Optional[dict]:
    conn = _connect()
    conn.execute("UPDATE organizations SET name=? WHERE id=?", (name, org_id))
    conn.commit()
    row = conn.execute("SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_org(org_id: int) -> bool:
    conn = _connect()
    # Unassign users first
    conn.execute("UPDATE users SET org_id=NULL WHERE org_id=?", (org_id,))
    cur = conn.execute("DELETE FROM organizations WHERE id=?", (org_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ── Scenarios ─────────────────────────────────────────────────────────────────

def save_scenario(user_id: int, name: str, tool: str, lat: float, lon: float,
                  state_json: str, response_json: str) -> int:
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO scenarios (user_id, name, tool, lat, lon, state_json, response_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, tool, lat, lon, state_json, response_json),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def list_scenarios(user_id: int, limit: int = 50) -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT id, name, tool, lat, lon, created_at
           FROM scenarios WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scenario(scenario_id: int, user_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM scenarios WHERE id=? AND user_id=?", (scenario_id, user_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_scenario(scenario_id: int, user_id: int) -> bool:
    conn = _connect()
    cur = conn.execute(
        "DELETE FROM scenarios WHERE id=? AND user_id=?", (scenario_id, user_id)
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ── Incidents ─────────────────────────────────────────────────────────────────

def create_incident(user_id: int, name: str, ics_number: str = "",
                    incident_type: str = "HazMat") -> dict:
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO incidents (user_id, name, ics_number, incident_type)
           VALUES (?, ?, ?, ?)""",
        (user_id, name, ics_number, incident_type),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM incidents WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


def list_incidents(user_id: int, limit: int = 50) -> list:
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM incidents WHERE user_id=?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_incident(incident_id: int, user_id: int, **fields) -> Optional[dict]:
    allowed = {"name", "ics_number", "incident_type", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None
    updates["updated_at"] = "datetime('now')"
    set_clause = ", ".join(
        f"{k}=datetime('now')" if k == "updated_at" else f"{k}=?"
        for k in updates
    )
    vals = [v for k, v in updates.items() if k != "updated_at"]
    vals += [incident_id, user_id]
    conn = _connect()
    conn.execute(
        f"UPDATE incidents SET {set_clause} WHERE id=? AND user_id=?", vals
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM incidents WHERE id=? AND user_id=?", (incident_id, user_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Facilities ────────────────────────────────────────────────────────────────

def list_facilities() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM facilities ORDER BY name COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_facility(name: str, facility_type: str, lat: float, lon: float,
                    chemical_id: Optional[str], default_rate_kg_min: Optional[float],
                    release_height_m: float, notes: str, created_by: int) -> dict:
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO facilities
           (name, facility_type, lat, lon, chemical_id, default_rate_kg_min,
            release_height_m, notes, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, facility_type, lat, lon, chemical_id, default_rate_kg_min,
         release_height_m, notes, created_by),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM facilities WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


def update_facility(facility_id: int, **fields) -> Optional[dict]:
    allowed = {"name", "facility_type", "lat", "lon", "chemical_id",
               "default_rate_kg_min", "release_height_m", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return None
    set_clause = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [facility_id]
    conn = _connect()
    conn.execute(f"UPDATE facilities SET {set_clause} WHERE id=?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM facilities WHERE id=?", (facility_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_facility(facility_id: int) -> bool:
    conn = _connect()
    cur = conn.execute("DELETE FROM facilities WHERE id=?", (facility_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted
