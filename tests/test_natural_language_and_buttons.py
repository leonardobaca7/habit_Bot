import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import init_db
from src.database.queries import add_or_update_user, create_habit, get_user_habits
from src.core.habits import get_main_reply_keyboard, format_streak_card
from src.services.ai_service import extract_habit_from_text, _heuristic_extract_habit

TEST_DB = "test_nl_buttons.db"


async def run_tests():
    print(">>> [Test 1] Testing ReplyKeyboardMarkup structure...")
    kb = get_main_reply_keyboard()
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    print("Found reply buttons count:", len(button_texts))
    assert "📋 Mis Hábitos de Hoy" in button_texts
    assert "➕ Agregar Hábito" in button_texts
    assert "🔥 Ver Racha" in button_texts
    assert kb.resize_keyboard is True
    assert kb.is_persistent is True
    print("ReplyKeyboardMarkup verified.")

    print("\n>>> [Test 2] Testing Streak Card Formatting...")
    card = format_streak_card(
        username="Leonardo",
        streak=7,
        last_completed_date="2026-10-06",
        habits=[{"title": "Leer 20 min", "completed": 1}],
    )
    assert "Panel de Racha de Leonardo" in card
    assert "7" in card
    print("Streak card formatting verified.")

    print("\n>>> [Test 3] Testing Heuristic Extraction...")
    h1 = _heuristic_extract_habit("Quiero leer 20 min")
    assert h1 == "Leer 20 min", f"Expected 'Leer 20 min', got '{h1}'"
    h2 = _heuristic_extract_habit("Voy a tomar 2L de agua")
    assert h2 == "Tomar 2L de agua", f"Expected 'Tomar 2L de agua', got '{h2}'"
    h3 = _heuristic_extract_habit("hola como estas")
    assert h3 is None, f"Casual greeting shouldn't be extracted, got '{h3}'"
    print("Heuristic patterns verified.")

    print("\n>>> [Test 4] Testing Gemini AI Natural Language Extraction...")
    res = await extract_habit_from_text("Quiero leer 20 min")
    print(f"Extracted from 'Quiero leer 20 min': '{res}'")
    assert res is not None
    assert "leer" in res.lower()

    # Test casual text (should not be a habit)
    res_casual = await extract_habit_from_text("hola qué tal")
    print(f"Extracted from casual greeting: '{res_casual}'")
    assert res_casual is None
    print("AI natural language extraction verified.")

    print("\n>>> [Test 5] Simulating Database Insertion from AI Extraction...")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db(TEST_DB)

    user_id = 554433
    await add_or_update_user(user_id, "nl_tester", db_path=TEST_DB)
    habit_id = await create_habit(user_id, res, db_path=TEST_DB)
    assert habit_id is not None

    habits = await get_user_habits(user_id, db_path=TEST_DB)
    assert len(habits) == 1
    assert habits[0]["title"] == res
    print(f"Habit #{habit_id} ('{res}') stored in SQLite successfully!")

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print("\n[OK] ALL NATURAL LANGUAGE AND BUTTON TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(run_tests())
