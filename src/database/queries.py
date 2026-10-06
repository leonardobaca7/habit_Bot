import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import aiosqlite
from src.database.db import get_db_connection

logger = logging.getLogger(__name__)


async def add_or_update_user(
    user_id: int,
    username: Optional[str] = None,
    timezone: str = "UTC",
    morning_hour: str = "08:00",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert user if not exists, or update username."""
    async with get_db_connection(db_path) as db:
        await db.execute(
            """
            INSERT INTO users (id, username, timezone, morning_hour, streak_count)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username);
            """,
            (user_id, username, timezone, morning_hour),
        )
        await db.commit()

        async with db.execute("SELECT * FROM users WHERE id = ?;", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}


async def get_user(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch user by Telegram ID."""
    async with get_db_connection(db_path) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?;", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_habit(
    user_id: int,
    title: str,
    frequency: str = "daily",
    time: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Create a new habit for the specified user with optional time."""
    async with get_db_connection(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO habits (user_id, title, frequency, time)
            VALUES (?, ?, ?, ?);
            """,
            (user_id, title.strip(), frequency, time),
        )
        await db.commit()
        return cursor.lastrowid


async def update_habit_time(
    habit_id: int,
    user_id: int,
    new_time: str,
    db_path: Optional[str] = None,
) -> bool:
    """Update scheduled time for a habit."""
    async with get_db_connection(db_path) as db:
        cursor = await db.execute(
            "UPDATE habits SET time = ? WHERE id = ? AND user_id = ?;",
            (new_time, habit_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_habit_by_id(
    habit_id: int,
    user_id: int,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch habit by ID and user ID."""
    async with get_db_connection(db_path) as db:
        async with db.execute(
            "SELECT * FROM habits WHERE id = ? AND user_id = ?;",
            (habit_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_habits(
    user_id: int,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all active habits for a user."""
    async with get_db_connection(db_path) as db:
        async with db.execute(
            "SELECT * FROM habits WHERE user_id = ? ORDER BY id ASC;",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def delete_habit(
    habit_id: int,
    user_id: int,
    db_path: Optional[str] = None,
) -> bool:
    """Delete a habit if it belongs to the user."""
    async with get_db_connection(db_path) as db:
        cursor = await db.execute(
            "DELETE FROM habits WHERE id = ? AND user_id = ?;",
            (habit_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_today_habits_status(
    user_id: int,
    date_str: str,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get user habits with their completion status for a specific date (YYYY-MM-DD).
    """
    async with get_db_connection(db_path) as db:
        async with db.execute(
            """
            SELECT 
                h.id AS habit_id,
                h.title,
                h.frequency,
                COALESCE(l.completed, 0) AS completed,
                l.checked_at
            FROM habits h
            LEFT JOIN daily_logs l 
                ON l.habit_id = h.id AND l.date = ?
            WHERE h.user_id = ?
            ORDER BY h.id ASC;
            """,
            (date_str, user_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def toggle_habit_log(
    habit_id: int,
    user_id: int,
    date_str: str,
    db_path: Optional[str] = None,
) -> bool:
    """
    Toggle habit completion status for given date.
    Returns the new completed boolean state.
    """
    async with get_db_connection(db_path) as db:
        # Check current log
        async with db.execute(
            "SELECT id, completed FROM daily_logs WHERE habit_id = ? AND date = ?;",
            (habit_id, date_str),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            current_status = bool(row["completed"])
            new_status = 0 if current_status else 1
            await db.execute(
                """
                UPDATE daily_logs 
                SET completed = ?, checked_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_status, row["id"]),
            )
        else:
            new_status = 1
            await db.execute(
                """
                INSERT INTO daily_logs (habit_id, user_id, date, completed, checked_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP);
                """,
                (habit_id, user_id, date_str),
            )

        await db.commit()
        return bool(new_status)


async def check_and_update_streak(
    user_id: int,
    date_str: str,
    db_path: Optional[str] = None,
) -> Tuple[bool, int, bool]:
    """
    Check if all habits for date_str are completed.
    If so, update user streak_count and last_completed_date.
    
    Returns:
        (all_completed: bool, current_streak: int, is_new_streak_day: bool)
    """
    habits = await get_today_habits_status(user_id, date_str, db_path=db_path)
    if not habits:
        return False, 0, False

    all_completed = all(bool(h["completed"]) for h in habits)

    user = await get_user(user_id, db_path=db_path)
    if not user:
        return False, 0, False

    streak = user.get("streak_count", 0)
    last_date = user.get("last_completed_date")

    if not all_completed:
        return False, streak, False

    # All habits are completed for today
    today_dt = datetime.strptime(date_str, "%Y-%m-%d")
    yesterday_str = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    # If already counted for today, do not increment streak again
    if last_date == date_str:
        return True, streak, False

    if last_date == yesterday_str:
        new_streak = streak + 1
    else:
        # Streak broken or first day
        new_streak = 1

    async with get_db_connection(db_path) as db:
        await db.execute(
            """
            UPDATE users 
            SET streak_count = ?, last_completed_date = ?
            WHERE id = ?;
            """,
            (new_streak, date_str, user_id),
        )
        await db.commit()

    logger.info(f"User {user_id} completed all habits! Streak updated to {new_streak}.")
    return True, new_streak, True


async def get_all_users(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all registered users."""
    async with get_db_connection(db_path) as db:
        async with db.execute("SELECT * FROM users ORDER BY id ASC;") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def has_notification_been_sent(
    user_id: int,
    date_str: str,
    notif_type: str,
    db_path: Optional[str] = None,
) -> bool:
    """Check if a notification of a given type was already sent to the user on date_str."""
    async with get_db_connection(db_path) as db:
        async with db.execute(
            """
            SELECT 1 FROM notification_logs 
            WHERE user_id = ? AND date = ? AND notif_type = ?;
            """,
            (user_id, date_str, notif_type),
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def record_notification_sent(
    user_id: int,
    date_str: str,
    notif_type: str,
    db_path: Optional[str] = None,
) -> None:
    """Record that a notification was sent to prevent duplicates."""
    async with get_db_connection(db_path) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO notification_logs (user_id, date, notif_type)
            VALUES (?, ?, ?);
            """,
            (user_id, date_str, notif_type),
        )
        await db.commit()

