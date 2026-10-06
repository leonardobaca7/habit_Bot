import asyncio
import os
import sys

# Ensure root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import init_db
from src.database.queries import (
    add_or_update_user,
    get_user,
    create_habit,
    get_user_habits,
    delete_habit,
    get_today_habits_status,
    toggle_habit_log,
    check_and_update_streak,
)
from src.core.habits import (
    format_status_message,
    build_status_keyboard,
    format_habits_list,
    build_habits_list_keyboard,
)
from src.core.streaks import get_user_today_str

TEST_DB = "test_phase2.db"


async def run_tests():
    print(">>> [Test 1] Initializing isolated database...")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    await init_db(TEST_DB)
    print("Database created.")

    print("\n>>> [Test 2] User Registration & Profile...")
    user_id = 99887766
    user = await add_or_update_user(
        user_id, username="test_duo", timezone="America/Lima", db_path=TEST_DB
    )
    assert user["id"] == user_id
    assert user["username"] == "test_duo"
    assert user["streak_count"] == 0
    print("User registration OK.")

    print("\n>>> [Test 3] Creating Habits...")
    h1 = await create_habit(user_id, "Tomar 2L de agua", db_path=TEST_DB)
    h2 = await create_habit(user_id, "Leer 10 min", db_path=TEST_DB)
    h3 = await create_habit(user_id, "Hacer flexiones", db_path=TEST_DB)
    habits = await get_user_habits(user_id, db_path=TEST_DB)
    assert len(habits) == 3
    print(f"Created 3 habits (IDs: {h1}, {h2}, {h3}). Habits retrieval OK.")

    print("\n>>> [Test 4] Status & Daily Logs...")
    today_str = get_user_today_str("America/Lima")
    status = await get_today_habits_status(user_id, today_str, db_path=TEST_DB)
    assert len(status) == 3
    assert all(h["completed"] == 0 for h in status)
    print("Initial daily status verified (all uncompleted).")

    print("\n>>> [Test 5] Toggling Habits...")
    # Toggle first habit to completed
    is_done = await toggle_habit_log(h1, user_id, today_str, db_path=TEST_DB)
    assert is_done is True

    # Partial completion streak check
    all_done, streak, is_new = await check_and_update_streak(user_id, today_str, db_path=TEST_DB)
    assert all_done is False
    assert streak == 0
    print("Partial completion streak check OK (all_done=False).")

    # Complete the rest of the habits
    await toggle_habit_log(h2, user_id, today_str, db_path=TEST_DB)
    await toggle_habit_log(h3, user_id, today_str, db_path=TEST_DB)

    # Check streak now that all 3 are completed
    all_done, streak, is_new = await check_and_update_streak(user_id, today_str, db_path=TEST_DB)
    assert all_done is True
    assert streak == 1
    assert is_new is True
    print(f"All habits completed! Streak incremented to {streak} (is_new={is_new}).")

    # Re-checking on the same day must not increment streak again
    all_done, streak_repeat, is_new_repeat = await check_and_update_streak(
        user_id, today_str, db_path=TEST_DB
    )
    assert streak_repeat == 1
    assert is_new_repeat is False
    print("Same-day re-check verified: streak remains 1 without double-incrementing.")

    # Simulating tomorrow
    tomorrow_str = "2026-10-06"
    # Complete all habits tomorrow
    await toggle_habit_log(h1, user_id, tomorrow_str, db_path=TEST_DB)
    await toggle_habit_log(h2, user_id, tomorrow_str, db_path=TEST_DB)
    await toggle_habit_log(h3, user_id, tomorrow_str, db_path=TEST_DB)
    all_done, streak_day2, is_new_day2 = await check_and_update_streak(
        user_id, tomorrow_str, db_path=TEST_DB
    )
    assert all_done is True
    assert streak_day2 == 2
    assert is_new_day2 is True
    print(f"Consecutive day completion verified! Streak progressed to {streak_day2}.")

    print("\n>>> [Test 6] UI Message Formatting & Keyboards...")
    msg = format_status_message(status, streak=2, date_str=today_str)
    assert "Tus H" in msg
    keyboard = build_status_keyboard(status)
    assert len(keyboard.inline_keyboard) == 4  # 3 habit rows + 1 utility row
    print("Status message and inline keyboard generated successfully.")

    list_msg = format_habits_list(habits)
    assert "Tomar 2L de agua" in list_msg
    list_keyboard = build_habits_list_keyboard(habits)
    assert len(list_keyboard.inline_keyboard) == 4  # 3 delete rows + 1 status button
    print("Habits list and inline keyboard generated successfully.")

    print("\n>>> [Test 7] Deleting Habit...")
    deleted = await delete_habit(h3, user_id, db_path=TEST_DB)
    assert deleted is True
    remaining_habits = await get_user_habits(user_id, db_path=TEST_DB)
    assert len(remaining_habits) == 2
    print("Habit deletion verified OK.")

    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print("\n[OK] ALL PHASE 2 TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
