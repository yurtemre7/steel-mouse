import os
import sqlite3
import sys
import time
import threading


def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.realpath(__file__))


DB_FILE = os.path.join(_get_app_dir(), "steelmouse.db")

_local = threading.local()


def _get_connection():
    if not hasattr(_local, 'connection') or _local.connection is None:
        _local.connection = sqlite3.connect(DB_FILE)
        _local.connection.row_factory = sqlite3.Row
    return _local.connection


def init_db():
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS battery_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            device_name TEXT NOT NULL,
            level INTEGER NOT NULL,
            is_charging INTEGER NOT NULL DEFAULT 0,
            timestamp REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_device_id ON battery_history(device_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON battery_history(timestamp)
    """)
    conn.commit()


def save_battery(device_id, device_name, level, is_charging, timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    conn = _get_connection()
    conn.execute(
        "INSERT INTO battery_history (device_id, device_name, level, is_charging, timestamp) VALUES (?, ?, ?, ?, ?)",
        (device_id, device_name, level, 1 if is_charging else 0, timestamp),
    )
    conn.commit()


def get_history(device_id=None, start_time=None, end_time=None, limit=100):
    conn = _get_connection()
    query = "SELECT * FROM battery_history WHERE 1=1"
    params = []
    if device_id:
        query += " AND device_id = ?"
        params.append(device_id)
    if start_time:
        query += " AND timestamp >= ?"
        params.append(start_time)
    if end_time:
        query += " AND timestamp <= ?"
        params.append(end_time)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_devices():
    conn = _get_connection()
    rows = conn.execute(
        "SELECT DISTINCT device_id, device_name FROM battery_history"
    ).fetchall()
    return [{"device_id": row["device_id"], "device_name": row["device_name"]} for row in rows]


def get_latest(device_id=None):
    conn = _get_connection()
    if device_id:
        row = conn.execute(
            "SELECT * FROM battery_history WHERE device_id = ? ORDER BY timestamp DESC LIMIT 1",
            (device_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM battery_history ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def close_db():
    if hasattr(_local, 'connection') and _local.connection is not None:
        _local.connection.close()
        _local.connection = None
