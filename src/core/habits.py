import html
from typing import List, Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from src.core.streaks import get_streak_emoji


def format_status_message(
    habits: List[Dict[str, Any]],
    streak: int,
    date_str: str,
) -> str:
    """Format the daily status report with checkboxes and streak counter in clean HTML."""
    if not habits:
        return (
            "🌱 <b>Aún no tienes hábitos registrados.</b>\n\n"
            "Comienza agregando uno usando:\n"
            "<code>/add_habit &lt;nombre del hábito&gt;</code>\n\n"
            "Ejemplo: <code>/add_habit Tomar 2L de agua</code>"
        )

    completed_count = sum(1 for h in habits if h.get("completed"))
    total_count = len(habits)
    pct = int((completed_count / total_count) * 100) if total_count > 0 else 0
    emoji = get_streak_emoji(streak)

    lines = [
        f"📅 <b>Tus Hábitos de Hoy</b> ({html.escape(date_str)})",
        f"🔥 <b>Racha activa:</b> {streak} días {emoji}",
        f"🎯 <b>Progreso:</b> {completed_count}/{total_count} ({pct}%)\n",
    ]

    for h in habits:
        check = "✅" if h.get("completed") else "⬜"
        safe_title = html.escape(str(h.get("title", "")))
        lines.append(f"[{check}] {safe_title}")

    if completed_count == total_count:
        lines.append("\n🌟 <b>¡Increíble! Has completado todos tus hábitos de hoy.</b>")
    else:
        lines.append("\n👇 <b>Toca los botones para marcar o desmarcar:</b>")

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
    """Format overall habits list in clean HTML."""
    if not habits:
        return (
            "🌱 <b>No tienes hábitos activos.</b>\n\n"
            "¡Crea el primero con <code>/add_habit &lt;nombre&gt;</code> para iniciar tu racha!"
        )

    lines = [f"📋 <b>Tus Hábitos Registrados</b> ({len(habits)}):\n"]
    for idx, h in enumerate(habits, start=1):
        freq = "Diario" if h.get("frequency") == "daily" else h.get("frequency", "Diario")
        safe_title = html.escape(str(h.get("title", "")))
        lines.append(f"{idx}. <b>{safe_title}</b> <i>({html.escape(str(freq))})</i>")

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


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Return persistent reply keyboard with main action buttons."""
    keyboard = [
        [KeyboardButton("📋 Mis Hábitos de Hoy")],
        [KeyboardButton("➕ Agregar Hábito"), KeyboardButton("🔥 Ver Racha")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


def format_streak_card(
    username: str,
    streak: int,
    last_completed_date: str,
    habits: List[Dict[str, Any]],
) -> str:
    """Format a detailed streak dashboard card."""
    emoji = get_streak_emoji(streak)
    completed_count = sum(1 for h in habits if h.get("completed"))
    total_count = len(habits)

    lines = [
        f"🔥 <b>Panel de Racha de {html.escape(username)}</b>\n",
        f"🔥 <b>Racha Actual:</b> {streak} días {emoji}",
        f"📅 <b>Último día completado:</b> {last_completed_date or 'Ninguno aún'}",
        f"🎯 <b>Progreso de hoy:</b> {completed_count}/{total_count} hábitos completados\n",
    ]

    if total_count == 0:
        lines.append("🌱 Agrega tu primer hábito con <b>➕ Agregar Hábito</b> para encender tu fuego.")
    elif completed_count == total_count:
        lines.append("🛡️ <b>¡Racha protegida hoy!</b> Mantén el ritmo mañana.")
    else:
        pending = total_count - completed_count
        lines.append(f"⚠️ Te faltan <b>{pending} hábito(s)</b> para no perder tu racha hoy. ¡Vamos!")

    return "\n".join(lines)

