"""
database.py — SQLite signal history and statistics.
Auto-creates tables on first run. No setup needed.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = "quetex_signals.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    """Create tables if not exist."""
    db = _conn()
    db.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            asset       TEXT NOT NULL,
            direction   TEXT NOT NULL,
            confidence  REAL NOT NULL,
            entry_price REAL NOT NULL,
            expiry      TEXT NOT NULL,
            timeframe   TEXT NOT NULL,
            pattern     TEXT DEFAULT '',
            buy_pct     REAL DEFAULT 0,
            sell_pct    REAL DEFAULT 0,
            adx_val     REAL DEFAULT 0,
            result      TEXT DEFAULT 'PENDING',
            created_at  TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()


def save(asset, direction, confidence, entry_price,
         expiry, timeframe, pattern="", buy_pct=0, sell_pct=0, adx=0) -> int:
    db = _conn()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur = db.execute("""
        INSERT INTO signals
        (asset,direction,confidence,entry_price,expiry,timeframe,
         pattern,buy_pct,sell_pct,adx_val,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (asset, direction, round(confidence, 2), entry_price,
          expiry, timeframe, pattern, round(buy_pct, 2),
          round(sell_pct, 2), round(adx, 2), ts))
    sid = cur.lastrowid
    db.commit()
    db.close()
    return sid


def mark_result(signal_id: int, result: str):
    db = _conn()
    db.execute("UPDATE signals SET result=? WHERE id=?", (result, signal_id))
    db.commit()
    db.close()


def get_recent(limit=20) -> list:
    db = _conn()
    rows = db.execute(
        "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    db = _conn()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total   = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    today_n = db.execute(
        "SELECT COUNT(*) FROM signals WHERE created_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]
    wins    = db.execute("SELECT COUNT(*) FROM signals WHERE result='WIN'").fetchone()[0]
    losses  = db.execute("SELECT COUNT(*) FROM signals WHERE result='LOSS'").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM signals WHERE result='PENDING'").fetchone()[0]
    db.close()
    wr = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0.0
    return {
        "total": total, "today": today_n,
        "wins": wins, "losses": losses,
        "pending": pending, "win_rate": wr
    }


def get_best_assets(limit=5) -> list:
    db = _conn()
    rows = db.execute("""
        SELECT asset,
          COUNT(*) as total,
          SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
          ROUND(SUM(CASE WHEN result='WIN' THEN 1.0 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN result IN('WIN','LOSS') THEN 1 ELSE 0 END),0)*100,1) as wr
        FROM signals
        GROUP BY asset HAVING total >= 3
        ORDER BY wr DESC LIMIT ?
    """, (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]
