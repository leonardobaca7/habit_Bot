import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import init_db
from src.database.queries import (
    add_or_update_user,
    create_habit,
    get_all_users,
    has_notification_been_sent,
    record_notification_sent,
)
from src.scheduler.jobs import calculate_rescue_hour
from src.services.ai_service import generate_rescue_message, _get_fallback_message

TEST_DB = "test_phase3.db"


async def run_phase3_tests():
    print(">>> [Test 1] Testing Rescue Hour Calculation (6.5 hours rule)...")
    assert calculate_rescue_hour("08:00") == "14:30", "08:00 + 6.5h should be 14:30"
    assert calculate_rescue_hour("07:00") == "13:30", "07:00 + 6.5h should be 13:30"
    assert calculate_rescue_hour("09:15") == "15:45", "09:15 + 6.5h should be 15:45"
    print("Rescue hour math verified (08:00 -> 14:30).")

    print("\n>>> [Test 2] Testing Notification Logs Database Table...")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db(TEST_DB)

    user = await add_or_update_user(112233, "tester_p3", db_path=TEST_DB)
    test_date = "2026-10-06"

    # Initially not sent
    sent = await has_notification_been_sent(112233, test_date, "morning", db_path=TEST_DB)
    assert sent is False

    # Record sent
    await record_notification_sent(112233, test_date, "morning", db_path=TEST_DB)
    sent_after = await has_notification_been_sent(112233, test_date, "morning", db_path=TEST_DB)
    assert sent_after is True

    # Check rescue type is still not sent
    sent_rescue = await has_notification_been_sent(112233, test_date, "rescue", db_path=TEST_DB)
    assert sent_rescue is False

    all_users = await get_all_users(db_path=TEST_DB)
    assert len(all_users) == 1
    print("Notification logs table & anti-duplicate queries verified.")

    print("\n>>> [Test 3] Testing Fallback Rescue Generator...")
    fallback = _get_fallback_message("Leonardo", ["Tomar 2L de agua"], 7)
    assert len(fallback) > 10
    assert "Leonardo" in fallback or "7" in fallback
    print("Fallback template generator OK.")

    print("\n>>> [Test 4] Testing Gemini AI Service Integration...")
    rescue_msg = await generate_rescue_message(
        username="Leonardo",
        pending_habits=["Tomar 2L de agua", "Leer 15 min"],
        current_streak=5,
    )
    print("Generated AI rescue message:\n" + rescue_msg.encode("ascii", "replace").decode("ascii"))
    assert len(rescue_msg) > 0
    assert len(rescue_msg) <= 350
    print("Gemini AI rescue message generated successfully!")

    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print("\n[OK] ALL PHASE 3 TESTS COMPLETED AND VERIFIED!")


if __name__ == "__main__":
    asyncio.run(run_phase3_tests())
