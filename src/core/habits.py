from typing import List, Dict, Any, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.core.streaks import get_streak_emoji


def format_status_message(
    habits: List[Dict[str, Any]],
    streak: int,
    date_str: str,
) -> str:
    """Format the daily status report with checkboxes and streak counter."""
    if not habits:
        return (
            "🌱 *Aún no tienes hábitos registrados.*\n\n"
            "Comienza agregando uno usando:\n"
            "`/add_habit <nombre del hábito>`\n\n"
            "Ejemplo: `/add_habit Tomar 2L de agua`"
        )

    completed_count = sum(1 for h in habits if h.get("completed"))
    total_count = len(habits)
    pct = int((completed_count / total_count) * 100) if total_count > 0 else 0
    emoji = get_streak_emoji(streak)

    lines = [
        f"📅 *Tus Hábitos de Hoy* ({date_str})",
        f"🔥 *Racha activa:* {streak} días {emoji}",
        f"🎯 *Progreso:* {completed_count}/{total_count} ({pct}%)\n",
    ]

    for h in habits:
        check = "✅" if h.get("completed") else "⬜"
        lines.append(f"[{check}] {h['title']}")

    if completed_count == total_count:
        lines.append("\n🌟 *¡Increíble! Has completado todos tus hábitos de hoy.*")
    else:
        lines.append("\n👇 *Toca los botones para marcar o desmarcar:*")

    return "\n".join(lines)


def build_status_keyboard(habits: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Build inline keyboard allowing toggling of each habit."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for h in habits:
        is_done = bool(h.get("completed"))
        icon = "✅" if is_done else "⬜"
        button_text = f"{icon} {h['title']}"
        callback_data = f"toggle_{h['habit_id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    # Utility row
    action_row = [
        InlineKeyboardButton("🔄 Actualizar", callback_data="status_refresh"),
        InlineKeyboardButton("📋 Ver Lista", callback_data="list_view"),
    ]
    keyboard.append(action_row)

    return InlineKeyboardMarkup(keyboard)


def format_habits_list(habits: List[Dict[str, Any]]) -> str:
    """Format overall habits list."""
    if not habits:
        return (
            "🌱 *No tienes hábitos activos.*\n\n"
            "¡Crea el primero con `/add_habit <nombre>` para iniciar tu racha!"
        )

    lines = [f"📋 *Tus Hábitos Registrados* ({len(habits)}):\n"]
    for idx, h in enumerate(habits, start=1):
        freq = "Diario" if h.get("frequency") == "daily" else h.get("frequency", "Diario")
        lines.append(f"{idx}. *{h['title']}* _({freq})_")

    lines.append("\n💡 Usa /status para revisar y marcar tus hábitos de hoy.")
    return "\n".join(lines)


def build_habits_list_keyboard(habits: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Build inline keyboard for habits list with management actions."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for h in habits:
        keyboard.append([
            InlineKeyboardButton(f"🗑 Eliminar: {h['title'][:20]}", callback_data=f"del_{h['id']}")
        ])

    keyboard.append([
        InlineKeyboardButton("📊 Ver Progreso de Hoy", callback_data="status_refresh")
    ])
    return InlineKeyboardMarkup(keyboard)
