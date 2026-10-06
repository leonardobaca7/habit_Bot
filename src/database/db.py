import os
import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = os.getenv("DATABASE_PATH", "habitbot.db")

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    timezone TEXT DEFAULT 'UTC',
    morning_hour TEXT DEFAULT '08:00',
    streak_count INTEGER DEFAULT 0,
    last_completed_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_HABITS_TABLE = """
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    frequency TEXT DEFAULT 'daily',
    time TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
"""

CREATE_DAILY_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    completed BOOLEAN DEFAULT 0,
    checked_at TIMESTAMP,
    FOREIGN KEY (habit_id) REFERENCES habits (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE(habit_id, date)
);
"""

CREATE_NOTIFICATION_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS notification_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    notif_type TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE(user_id, date, notif_type)
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_habits_user_id ON habits(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_logs_user_date ON daily_logs(user_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_logs_habit_date ON daily_logs(habit_id, date);
CREATE INDEX IF NOT EXISTS idx_notif_logs ON notification_logs(user_id, date, notif_type);
"""


def get_db_path(db_path: Optional[str] = None) -> str:
    """Return configured database path or default."""
    return db_path or os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH)


@asynccontextmanager
async def get_db_connection(db_path: Optional[str] = None) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Async context manager for SQLite database connection.
    Enables foreign keys and sets Row factory.
    """
    target_path = get_db_path(db_path)
    db = await aiosqlite.connect(target_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    try:
        yield db
    finally:
        await db.close()


async def init_db(db_path: Optional[str] = None) -> None:
    """
    Initialize SQLite database schema and indexes.
    Creates tables: users, habits, daily_logs if they do not exist.
    """
    target_path = get_db_path(db_path)
    logger.info(f"Initializing database at: {target_path}")

    async with get_db_connection(target_path) as db:
        await db.execute(CREATE_USERS_TABLE)
        await db.execute(CREATE_HABITS_TABLE)
        await db.execute(CREATE_DAILY_LOGS_TABLE)
        await db.execute(CREATE_NOTIFICATION_LOGS_TABLE)
        await db.executescript(CREATE_INDEXES)

        # Migration: ensure 'time' column exists in 'habits'
        async with db.execute("PRAGMA table_info(habits);") as cursor:
            cols = [row["name"] for row in await cursor.fetchall()]
            if "time" not in cols:
                await db.execute("ALTER TABLE habits ADD COLUMN time TEXT DEFAULT NULL;")

        await db.commit()

    logger.info("Database initialized successfully with all tables and indexes.")


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_db())
