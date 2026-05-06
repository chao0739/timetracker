"""
数据访问层 (Data Access Layer)
- 封装 SQLite 操作
- 所有表都带 user_id 列, 本地版默认填 1, 未来上云改成真实用户 ID 即可零迁移
- 这一层不含任何业务逻辑, 只做 CRUD
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# 本地版固定用户 ID, 上云后这个常量会被废弃, 改成从 session 取
LOCAL_USER_ID = 1


class Database:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._ensure_default_user()

    def _init_schema(self):
        cur = self.conn.cursor()

        # 用户表 (本地版只有一个用户, 未来上云直接扩展)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)

        # 用户偏好: 时区列表, 番茄钟设置等. 用 key-value 方便扩展
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 计时器主表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS timers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                total_seconds INTEGER NOT NULL DEFAULT 0,
                is_running INTEGER NOT NULL DEFAULT 0,
                last_start_ts TEXT,
                last_checkpoint_ts TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (user_id, name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_timers_user ON timers(user_id)")

        # 会话日志: 每次启动到停止算一条
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timer_id INTEGER NOT NULL,
                start_ts TEXT NOT NULL,
                end_ts TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                FOREIGN KEY (timer_id) REFERENCES timers(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_timer ON sessions(timer_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_ts)")

        # 番茄钟会话日志 (独立于普通计时器)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pomodoros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                phase TEXT NOT NULL,        -- work / short_break / long_break
                start_ts TEXT NOT NULL,
                end_ts TEXT NOT NULL,
                planned_seconds INTEGER NOT NULL,
                actual_seconds INTEGER NOT NULL,
                completed INTEGER NOT NULL,  -- 1=自然结束, 0=被中途取消
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pomo_user ON pomodoros(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pomo_start ON pomodoros(start_ts)")

        self.conn.commit()

    def _ensure_default_user(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM users WHERE id=?", (LOCAL_USER_ID,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (id, username, created_at) VALUES (?, ?, ?)",
                (LOCAL_USER_ID, "local", datetime.now(timezone.utc).isoformat())
            )
            self.conn.commit()

    # ---------- 用户偏好 ----------
    def get_pref(self, user_id: int, key: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM user_prefs WHERE user_id=? AND key=?", (user_id, key))
        row = cur.fetchone()
        return row["value"] if row else None

    def set_pref(self, user_id: int, key: str, value: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO user_prefs (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
            (user_id, key, value)
        )
        self.conn.commit()

    # ---------- 计时器 ----------
    def list_timers(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM timers WHERE user_id=? ORDER BY id ASC", (user_id,))
        return cur.fetchall()

    def get_timer(self, user_id: int, timer_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM timers WHERE id=? AND user_id=?", (timer_id, user_id))
        return cur.fetchone()

    def add_timer(self, user_id: int, name: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO timers (user_id, name, created_at) VALUES (?, ?, ?)",
            (user_id, name, datetime.now(timezone.utc).isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def rename_timer(self, user_id: int, timer_id: int, new_name: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE timers SET name=? WHERE id=? AND user_id=?", (new_name, timer_id, user_id))
        self.conn.commit()

    def delete_timer(self, user_id: int, timer_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM timers WHERE id=? AND user_id=?", (timer_id, user_id))
        self.conn.commit()

    def mark_timer_running(self, timer_id: int, now_iso: str):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE timers SET is_running=1, last_start_ts=?, last_checkpoint_ts=? WHERE id=?",
            (now_iso, now_iso, timer_id)
        )
        self.conn.commit()

    def update_timer_progress(self, timer_id: int, add_seconds: int, new_checkpoint_iso: str):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE timers SET total_seconds=total_seconds+?, last_checkpoint_ts=? WHERE id=?",
            (add_seconds, new_checkpoint_iso, timer_id)
        )
        self.conn.commit()

    def mark_timer_stopped(self, timer_id: int, add_seconds: int):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE timers SET total_seconds=total_seconds+?, is_running=0, "
            "last_start_ts=NULL, last_checkpoint_ts=NULL WHERE id=?",
            (add_seconds, timer_id)
        )
        self.conn.commit()

    def list_running_timers(self, user_id: Optional[int] = None):
        """列出所有运行中的计时器, user_id=None 时返回所有用户的(用于启动时全局恢复)"""
        cur = self.conn.cursor()
        if user_id is None:
            cur.execute("SELECT * FROM timers WHERE is_running=1")
        else:
            cur.execute("SELECT * FROM timers WHERE is_running=1 AND user_id=?", (user_id,))
        return cur.fetchall()

    def add_session(self, user_id: int, timer_id: int, start_iso: str, end_iso: str, duration: int):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO sessions (user_id, timer_id, start_ts, end_ts, duration_seconds) VALUES (?, ?, ?, ?, ?)",
            (user_id, timer_id, start_iso, end_iso, duration)
        )
        self.conn.commit()

    def query_sessions(self, user_id: int, timer_id: int, start_iso: str, end_iso: str):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT start_ts, end_ts, duration_seconds FROM sessions
            WHERE user_id=? AND timer_id=? AND end_ts >= ? AND start_ts <= ?
        """, (user_id, timer_id, start_iso, end_iso))
        return cur.fetchall()

    def export_all_sessions(self, user_id: int):
        """导出指定用户的全部会话日志"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT t.name, s.start_ts, s.end_ts, s.duration_seconds
            FROM sessions s JOIN timers t ON s.timer_id = t.id
            WHERE s.user_id=?
            ORDER BY s.start_ts ASC
        """, (user_id,))
        return cur.fetchall()

    # ---------- 番茄钟 ----------
    def add_pomodoro(self, user_id: int, phase: str, start_iso: str, end_iso: str,
                     planned: int, actual: int, completed: bool):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO pomodoros (user_id, phase, start_ts, end_ts, planned_seconds, actual_seconds, completed) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, phase, start_iso, end_iso, planned, actual, 1 if completed else 0)
        )
        self.conn.commit()

    def count_completed_work_pomodoros_today(self, user_id: int, day_start_iso: str, now_iso: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS c FROM pomodoros "
            "WHERE user_id=? AND phase='work' AND completed=1 AND end_ts >= ? AND end_ts <= ?",
            (user_id, day_start_iso, now_iso)
        )
        return cur.fetchone()["c"]

    def close(self):
        self.conn.close()
