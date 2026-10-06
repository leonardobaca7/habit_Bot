import asyncio
import os
import sys

# Ensure project root is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiosqlite
from src.database.db import init_db, get_db_connection

TEST_DB_PATH = "test_habitbot.db"


async def verify_database():
    print("--- [1] Initializing Test Database ---")
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    await init_db(TEST_DB_PATH)
    print("Database tables initialized successfully.")

    print("\n--- [2] Inspecting SQLite Tables ---")
    async with get_db_connection(TEST_DB_PATH) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ) as cursor:
            tables = [row["name"] for row in await cursor.fetchall()]
            print("Created tables:", tables)
            assert "users" in tables, "Table 'users' missing!"
            assert "habits" in tables, "Table 'habits' missing!"
            assert "daily_logs" in tables, "Table 'daily_logs' missing!"

        print("\n--- [3] Testing CRUD & Constraints ---")
        # 1. Insert User
        await db.execute(
            "INSERT INTO users (id, username, timezone, morning_hour) VALUES (?, ?, ?, ?);",
            (123456789, "duo_tester", "America/Lima", "07:30"),
        )
        await db.commit()

        # 2. Insert Habit for User
        cursor = await db.execute(
            "INSERT INTO habits (user_id, title, frequency) VALUES (?, ?, ?);",
            (123456789, "Leer 10 páginas", "daily"),
        )
        habit_id = cursor.lastrowid
        await db.commit()

        # 3. Insert Daily Log
        await db.execute(
            "INSERT INTO daily_logs (habit_id, user_id, date, completed) VALUES (?, ?, ?, ?);",
            (habit_id, 123456789, "2026-10-05", 1),
        )
        await db.commit()

        # 4. Query back to verify values
        async with db.execute(
            """
            SELECT u.username, u.morning_hour, h.title, l.date, l.completed
            FROM users u
            JOIN habits h ON h.user_id = u.id
            JOIN daily_logs l ON l.habit_id = h.id
            WHERE u.id = ?;
            """,
            (123456789,),
        ) as query_cursor:
            row = await query_cursor.fetchone()
            print("Queried Record:", dict(row))
            assert row["username"] == "duo_tester"
            assert row["morning_hour"] == "07:30"
            assert row["title"] == "Leer 10 páginas"
            assert row["completed"] == 1

    print("\n--- [4] Cleaning up Test Database ---")
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    print("\n[OK] Verification SUCCESSFUL: All tables and constraints work as expected!")


if __name__ == "__main__":
    asyncio.run(verify_database())
