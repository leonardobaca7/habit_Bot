import html
import logging
from typing import Optional
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

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
from src.core.streaks import get_user_today_str, get_congratulations_message
from src.core.habits import (
    format_status_message,
    build_status_keyboard,
    format_habits_list,
    build_habits_list_keyboard,
)

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command. Register user and send welcome message."""
    user = update.effective_user
    if not user or not update.message:
        return

    # Register or update user in database
    await add_or_update_user(
        user_id=user.id,
        username=user.username,
        timezone="UTC",
        morning_hour="08:00",
    )

    first_name = html.escape(user.first_name or "Amigo")
    welcome_text = (
        f"🦉 <b>¡Hola, {first_name}! Bienvenido a HabitBot.</b>\n\n"
        "Soy tu coach diario de hábitos. Mi misión es ayudarte "
        "a construir disciplina paso a paso y mantener viva tu racha 🔥.\n\n"
        "📋 <b>Comandos disponibles:</b>\n"
        "• <code>/add_habit &lt;nombre&gt;</code> — Crea un nuevo hábito diario.\n"
        "• <code>/status</code> — Mira tu progreso de hoy y marca tus hábitos.\n"
        "• <code>/list</code> — Consulta y administra tu lista de hábitos.\n"
        "• <code>/help</code> — Instrucciones y consejos sobre tus rachas.\n\n"
        "💡 <b>¿Listo para empezar?</b>\n"
        "Agrega tu primer hábito escribiendo:\n"
        "<code>/add_habit Tomar 2L de agua</code>"
    )

    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


async def add_habit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add_habit command. Adds a habit with arguments or gives instructions."""
    user = update.effective_user
    if not user or not update.message:
        return

    if not context.args:
        instruction_text = (
            "💡 <b>¿Cómo agregar un hábito?</b>\n\n"
            "Escribe el nombre del hábito después del comando.\n\n"
            "<b>Ejemplos:</b>\n"
            "• <code>/add_habit Tomar 2L de agua</code>\n"
            "• <code>/add_habit Leer 15 min</code>\n"
            "• <code>/add_habit Hacer 20 flexiones</code>\n"
            "• <code>/add_habit Meditar 10 min</code>\n\n"
            "¡Elige algo simple para asegurar tu racha diaria! 🔥"
        )
        await update.message.reply_text(instruction_text, parse_mode=ParseMode.HTML)
        return

    title = " ".join(context.args).strip()
    if len(title) > 100:
        await update.message.reply_text(
            "⚠️ El nombre del hábito es muy largo (máximo 100 caracteres). Intenta uno más conciso."
        )
        return

    # Ensure user exists
    await add_or_update_user(user.id, user.username)

    habit_id = await create_habit(user.id, title, frequency="daily")
    logger.info(f"User {user.id} created habit #{habit_id}: '{title}'")

    safe_title = html.escape(title)
    response_text = (
        "✅ <b>¡Hábito agregado con éxito!</b>\n\n"
        f"📌 <b>{safe_title}</b>\n\n"
        "Usa /status para marcar tu avance de hoy y comenzar a sumar días en tu racha 🔥."
    )
    await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command. Displays all registered habits with inline actions."""
    user = update.effective_user
    if not user or not update.message:
        return

    habits = await get_user_habits(user.id)
    text = format_habits_list(habits)
    keyboard = build_habits_list_keyboard(habits) if habits else None

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command. Displays today's status checklist with interactive buttons."""
    user = update.effective_user
    if not user or not update.message:
        return

    db_user = await get_user(user.id)
    tz = db_user.get("timezone", "UTC") if db_user else "UTC"
    streak = db_user.get("streak_count", 0) if db_user else 0
    today_str = get_user_today_str(tz)

    habits = await get_today_habits_status(user.id, today_str)
    text = format_status_message(habits, streak, today_str)
    keyboard = build_status_keyboard(habits) if habits else None

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button clicks for habit toggling, status refresh, and deletions."""
    query = update.callback_query
    if not query:
        return

    user = update.effective_user
    if not user:
        await query.answer()
        return

    data = query.data or ""
    db_user = await get_user(user.id)
    tz = db_user.get("timezone", "UTC") if db_user else "UTC"
    today_str = get_user_today_str(tz)

    # 1. Toggle Habit Completion
    if data.startswith("toggle_"):
        try:
            habit_id = int(data.split("_")[1])
        except (ValueError, IndexError):
            await query.answer("Error al procesar la acción.")
            return

        new_status = await toggle_habit_log(habit_id, user.id, today_str)
        all_completed, streak, is_new_streak_day = await check_and_update_streak(user.id, today_str)

        if all_completed and is_new_streak_day:
            alert_text = f"🎉 ¡Racha protegida! Llevas {streak} días consecutivos 🔥"
            await query.answer(alert_text, show_alert=True)
            congrats = get_congratulations_message(streak)
            if query.message:
                await query.message.reply_text(congrats, parse_mode=ParseMode.HTML)
        else:
            toast = "Completado ✅" if new_status else "Desmarcado ⬜"
            await query.answer(toast)

        # Refresh status view
        updated_habits = await get_today_habits_status(user.id, today_str)
        updated_user = await get_user(user.id)
        current_streak = updated_user.get("streak_count", 0) if updated_user else 0

        new_text = format_status_message(updated_habits, current_streak, today_str)
        new_keyboard = build_status_keyboard(updated_habits)

        try:
            await query.edit_message_text(
                text=new_text,
                reply_markup=new_keyboard,
                parse_mode=ParseMode.HTML,
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error updating message: {e}")

    # 2. Refresh Status
    elif data == "status_refresh":
        await query.answer("Actualizado 🔄")
        habits = await get_today_habits_status(user.id, today_str)
        current_streak = db_user.get("streak_count", 0) if db_user else 0
        text = format_status_message(habits, current_streak, today_str)
        keyboard = build_status_keyboard(habits) if habits else None

        try:
            await query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error refreshing status: {e}")

    # 3. View Habits List
    elif data == "list_view":
        await query.answer()
        habits = await get_user_habits(user.id)
        text = format_habits_list(habits)
        keyboard = build_habits_list_keyboard(habits) if habits else None

        try:
            await query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error switching to list view: {e}")

    # 4. Delete Habit
    elif data.startswith("del_"):
        try:
            habit_id = int(data.split("_")[1])
        except (ValueError, IndexError):
            await query.answer("Error al eliminar el hábito.")
            return

        deleted = await delete_habit(habit_id, user.id)
        if deleted:
            await query.answer("🗑 Hábito eliminado con éxito.")
        else:
            await query.answer("No se pudo eliminar el hábito.")

        habits = await get_user_habits(user.id)
        text = format_habits_list(habits)
        keyboard = build_habits_list_keyboard(habits) if habits else None

        try:
            await query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error updating message after delete: {e}")

    else:
        await query.answer()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return

    help_text = (
        "🦉 <b>Guía de HabitBot: Coach de Hábitos</b>\n\n"
        "HabitBot se basa en la consistencia de pequeñas acciones diarias para generar grandes cambios.\n\n"
        "🔥 <b>Reglas de la Racha:</b>\n"
        "1. Completa <b>todos</b> tus hábitos registrados antes de la medianoche.\n"
        "2. Al completar el último hábito, tu racha aumentará en +1 día.\n"
        "3. Si un día no completas tus hábitos, tu racha volverá a 0. ¡No dejes que se apague el fuego!\n\n"
        "📌 <b>Lista de Comandos:</b>\n"
        "• <code>/start</code> — Inicia o reinicia tu perfil.\n"
        "• <code>/add_habit &lt;nombre&gt;</code> — Agrega un hábito diario.\n"
        "• <code>/status</code> — Abre tu tablero diario interactivo con casillas de verificación.\n"
        "• <code>/list</code> — Mira tus hábitos y elimina los que ya no necesites.\n"
        "• <code>/help</code> — Muestra esta ayuda.\n"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
