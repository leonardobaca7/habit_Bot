"""Database layer for HabitBot using aiosqlite."""
from .db import init_db, get_db_connection
from .queries import (
    add_or_update_user,
    get_user,
    create_habit,
    get_user_habits,
    delete_habit,
    get_today_habits_status,
    toggle_habit_log,
    check_and_update_streak,
    get_all_users,
    has_notification_been_sent,
    record_notification_sent,
)

__all__ = [
    "init_db",
    "get_db_connection",
    "add_or_update_user",
    "get_user",
    "create_habit",
    "get_user_habits",
    "delete_habit",
    "get_today_habits_status",
    "toggle_habit_log",
    "check_and_update_streak",
    "get_all_users",
    "has_notification_been_sent",
    "record_notification_sent",
]
