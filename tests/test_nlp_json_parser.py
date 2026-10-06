import asyncio
import os
import sys

# Ensure root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import init_db
from src.database.queries import (
    add_or_update_user,
    create_habit,
    update_habit_time,
    get_habit_by_id,
    get_user_habits,
)
from src.services.ai_service import parse_habit_intent, _heuristic_parse_habit_intent

TEST_DB = "test_nlp_json.db"


async def run_nlp_tests():
    print(">>> [Test 1] Testing Fallback Heuristic Parser...")
    h1 = _heuristic_parse_habit_intent("Quiero leer 20 min a las 22:00")
    assert h1["es_habito"] is True
    assert "Leer 20 min" in h1["titulo"]
    assert h1["hora"] == "22:00"

    h2 = _heuristic_parse_habit_intent("Tomar 2L de agua")
    assert h2["es_habito"] is True
    assert h2["hora"] is None

    h3 = _heuristic_parse_habit_intent("Hola cómo estás hoy?")
    assert h3["es_habito"] is False
    print("Heuristic fallback parser verified.")

    print("\n>>> [Test 2] Testing Gemini API parse_habit_intent JSON Schema...")
    # Test 2.1: Habit with hour
    res1 = await parse_habit_intent("Quiero leer 20 min todas las noches a las 22:00")
    print("Result 1 (with hour):", res1)
    assert res1["es_habito"] is True
    assert "leer" in res1["titulo"].lower()
    assert res1["hora"] in ["22:00", "22:00:00"]

    # Test 2.2: Habit without hour
    res2 = await parse_habit_intent("Tomar 2 litros de agua")
    print("Result 2 (without hour):", res2)
    assert res2["es_habito"] is True
    assert res2["hora"] is None or res2["hora"] == ""

    # Test 2.3: Casual text (not a habit)
    res3 = await parse_habit_intent("Hola, buen día")
    print("Result 3 (casual text):", res3)
    assert res3["es_habito"] is False
    print("Gemini NLP JSON schema parser verified successfully!")

    print("\n>>> [Test 3] Testing Database Time Migration & Updates...")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db(TEST_DB)

    user_id = 887766
    await add_or_update_user(user_id, "json_tester", db_path=TEST_DB)

    # Insert habit with custom time
    hid = await create_habit(user_id, res1["titulo"], frequency="diario", time="22:00", db_path=TEST_DB)
    habit = await get_habit_by_id(hid, user_id, db_path=TEST_DB)
    assert habit["time"] == "22:00"

    # Update habit time (as triggered by button)
    updated = await update_habit_time(hid, user_id, "08:00", db_path=TEST_DB)
    assert updated is True
    habit_after = await get_habit_by_id(hid, user_id, db_path=TEST_DB)
    assert habit_after["time"] == "08:00"
    print("Habit time insertion and update verified.")

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print("\n[OK] ALL NLP JSON PARSER TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_nlp_tests())
