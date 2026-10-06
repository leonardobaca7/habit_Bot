import html
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.database.queries import (
    add_or_update_user,
    get_user,
    create_habit,
    update_habit_time,
    get_habit_by_id,
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
    get_main_reply_keyboard,
    format_streak_card,
)
from src.scheduler.jobs import (
    send_morning_notification,
    send_rescue_notification,
    send_weekly_report,
)
from src.services.ai_service import (
    extract_habit_from_text,
    parse_habit_intent,
    classify_and_parse_intent,
    generate_coach_reply,
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
        "💡 <b>¡Ya no dependes de comandos!</b>\n"
        "Puedes usar los botones de acceso rápido que aparecen abajo o simplemente "
        "<b>escribir en el chat lo que deseas hacer</b> (por ejemplo: <i>'Quiero leer 20 min'</i> o <i>'Tomar 2L de agua'</i>) "
        "y mi Inteligencia Artificial lo registrará automáticamente. 🤖✨\n\n"
        "🔘 <b>Botones principales:</b>\n"
        "• <b>📋 Mis Hábitos:</b> Tu tablero interactivo diario con casillas.\n"
        "• <b>📊 Mi Semana:</b> Reporte semanal y estadísticas de cumplimiento.\n"
        "• <b>➕ Agregar Hábito:</b> Guía para crear nuevas metas con IA.\n"
        "• <b>⚡ Probar Alerta:</b> Simula la alerta de rescate de racha."
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_reply_keyboard(),
        parse_mode=ParseMode.HTML,
    )


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

    # 5. Change Habit Time
    elif data.startswith("change_time_"):
        try:
            habit_id = int(data.split("_")[2])
        except (ValueError, IndexError):
            await query.answer("Error al cambiar horario.")
            return

        habit = await get_habit_by_id(habit_id, user.id)
        if not habit:
            await query.answer("Hábito no encontrado.")
            return

        await query.answer()
        safe_title = html.escape(habit["title"])
        time_buttons = [
            [
                InlineKeyboardButton("🌅 07:00", callback_data=f"set_time_{habit_id}_07:00"),
                InlineKeyboardButton("☀️ 08:00", callback_data=f"set_time_{habit_id}_08:00"),
                InlineKeyboardButton("🌤 12:00", callback_data=f"set_time_{habit_id}_12:00"),
            ],
            [
                InlineKeyboardButton("⛅ 16:00", callback_data=f"set_time_{habit_id}_16:00"),
                InlineKeyboardButton("🌙 20:00", callback_data=f"set_time_{habit_id}_20:00"),
                InlineKeyboardButton("🌙 22:00", callback_data=f"set_time_{habit_id}_22:00"),
            ],
            [
                InlineKeyboardButton("🔙 Volver al Tablero", callback_data="status_refresh")
            ]
        ]
        await query.edit_message_text(
            text=f"⏰ <b>Selecciona el horario de recordatorio para:</b>\n📌 <b>{safe_title}</b>",
            reply_markup=InlineKeyboardMarkup(time_buttons),
            parse_mode=ParseMode.HTML,
        )

    # 6. Set Specific Habit Time
    elif data.startswith("set_time_"):
        try:
            parts = data.split("_")
            habit_id = int(parts[2])
            new_time = parts[3]
        except (ValueError, IndexError):
            await query.answer("Error al actualizar la hora.")
            return

        await update_habit_time(habit_id, user.id, new_time)
        habit = await get_habit_by_id(habit_id, user.id)
        title = habit["title"] if habit else "Hábito"
        await query.answer(f"¡Recordatorio fijado a las {new_time}! ⏰✅")

        safe_title = html.escape(title)
        back_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Ver Tablero de Hoy", callback_data="status_refresh")]
        ])
        await query.edit_message_text(
            text=(
                f"✅ <b>¡Horario configurado con éxito!</b>\n\n"
                f"📌 <b>Hábito:</b> {safe_title}\n"
                f"⏰ <b>Nuevo recordatorio:</b> {new_time}\n\n"
                "Te enviaremos una notificación cuando llegue tu hora. 🔥"
            ),
            reply_markup=back_keyboard,
            parse_mode=ParseMode.HTML,
        )

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


async def test_morning_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual trigger to test morning notification immediately."""
    user = update.effective_user
    if not user or not update.message:
        return

    db_user = await get_user(user.id)
    if not db_user:
        await update.message.reply_text("Primero usa /start para registrarte.")
        return

    sent = await send_morning_notification(context.bot, db_user, force=True)
    if not sent:
        await update.message.reply_text(
            "⚠️ No tienes hábitos configurados. Agrega uno con <code>/add_habit &lt;nombre&gt;</code>.",
            parse_mode=ParseMode.HTML,
        )


async def test_duolingo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manual trigger to force Gemini Duolingo rescue alert immediately.
    Generates AI push reminder with interactive buttons without waiting 6.5h.
    """
    user = update.effective_user
    if not user or not update.message:
        return

    db_user = await get_user(user.id)
    if not db_user:
        await update.message.reply_text("Primero usa /start para registrarte.")
        return

    sent = await send_rescue_notification(context.bot, db_user, force=True)
    if not sent:
        await update.message.reply_text(
            "🌟 ¡No tienes hábitos pendientes para hoy o no tienes hábitos registrados!\n\n"
            "Para probar la alerta de rescate de racha, asegúrate de tener al menos un hábito sin completar.",
            parse_mode=ParseMode.HTML,
        )


# Backward compatibility alias
test_rescue_command = test_duolingo_command


async def test_weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manual trigger to force weekly report immediately.
    Calculates 7-day SQLite completion statistics and generates Gemini feedback.
    """
    user = update.effective_user
    if not user or not update.message:
        return

    db_user = await get_user(user.id)
    if not db_user:
        await update.message.reply_text("Primero usa /start para registrarte.")
        return

    sent = await send_weekly_report(context.bot, db_user, force=True)
    if not sent:
        await update.message.reply_text(
            "⚠️ No se pudo generar el reporte semanal. Asegúrate de tener al menos un hábito registrado con /add_habit.",
            parse_mode=ParseMode.HTML,
        )


async def process_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Central AI Intent Router and Message Handler.
    Intercepts all incoming text messages, classifies user intention via Gemini API NLP:
    - VER_REPORTE: Weekly statistics calculation and personalized Gemini feedback
    - VER_ESTADO: Daily checklist board with interactive check/uncheck buttons
    - PROBAR_ALERTA: Immediate Duolingo rescue notification trigger
    - CREAR_HABITO: Automatic habit title, frequency and time extraction & registration
    - CONVERSACION_GENERAL: Sarcastic/motivational Duolingo coach response
    """
    user = update.effective_user
    if not user or not update.message:
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    # Ensure user is registered
    db_user = await add_or_update_user(user.id, user.username)

    # 1. Quick helper button: "➕ Agregar Hábito"
    if text == "➕ Agregar Hábito":
        prompt_text = (
            "✏️ <b>¿Qué nuevo hábito te gustaría construir?</b>\n\n"
            "Simplemente escríbeme lo que tienes en mente con o sin hora. Por ejemplo:\n"
            "• <i>Leer 20 min todas las noches a las 22:00</i>\n"
            "• <i>Tomar 2L de agua</i>\n"
            "• <i>Meditar 10 min a las 07:30</i>\n"
            "• <i>Hacer 30 flexiones al despertar</i>\n\n"
            "🤖 <b>Nuestra IA con Gemini</b> extraerá el título, frecuencia y hora automáticamente."
        )
        await update.message.reply_text(
            prompt_text,
            reply_markup=get_main_reply_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    # Send typing action to Telegram
    await update.message.chat.send_action("typing")

    # 2. AI Intent Router with Gemini
    intent_data = await classify_and_parse_intent(text)
    intent = intent_data.get("intencion", "CONVERSACION_GENERAL")
    logger.info(f"User {user.id} message: '{text}' -> Intent: {intent}")

    # Case A: VER_REPORTE
    if intent == "VER_REPORTE":
        sent = await send_weekly_report(context.bot, db_user, force=True)
        if not sent:
            await update.message.reply_text(
                "🌱 <b>No tienes hábitos activos</b> para generar el reporte semanal.\n\n"
                "¡Agrega tu primer hábito escribiéndolo o con <b>➕ Agregar Hábito</b>!",
                reply_markup=get_main_reply_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        return

    # Case B: VER_ESTADO
    elif intent == "VER_ESTADO":
        await status_command(update, context)
        return

    # Case C: PROBAR_ALERTA
    elif intent == "PROBAR_ALERTA":
        sent = await send_rescue_notification(context.bot, db_user, force=True)
        if not sent:
            await update.message.reply_text(
                "🌟 ¡No tienes hábitos pendientes para hoy o no tienes hábitos registrados!\n\n"
                "Para probar la alerta de rescate de racha, asegúrate de tener al menos un hábito sin completar.",
                reply_markup=get_main_reply_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        return

    # Case D: CREAR_HABITO
    elif intent == "CREAR_HABITO":
        datos = intent_data.get("datos_habito", {})
        title = (datos.get("titulo") or "").strip()

        if not title or len(title) < 2:
            reply = await generate_coach_reply(user.first_name or user.username or "Amigo", text)
            await update.message.reply_text(
                html.escape(reply),
                reply_markup=get_main_reply_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if len(title) > 100:
            title = title[:100]

        frequency = datos.get("frecuencia") or "diario"
        time = datos.get("hora")
        if not time:
            time = db_user.get("morning_hour", "08:00") or "08:00"

        habit_id = await create_habit(user.id, title, frequency=frequency, time=time)
        logger.info(f"AI registered habit #{habit_id} for user {user.id}: '{title}' at {time} ({frequency})")

        safe_title = html.escape(title)
        safe_time = html.escape(time)
        safe_freq = html.escape(frequency)

        confirm_text = (
            "✅ <b>¡Hábito registrado!</b>\n\n"
            f"📌 <b>Hábito:</b> {safe_title}\n"
            f"⏰ <b>Horario:</b> {safe_time} ({safe_freq})\n\n"
            "¿Deseas ajustar la hora?"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Cambiar hora", callback_data=f"change_time_{habit_id}")],
            [InlineKeyboardButton("📊 Ver Tablero de Hoy", callback_data="status_refresh")],
        ])

        await update.message.reply_text(
            confirm_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        return

    # Case E: CONVERSACION_GENERAL (Default)
    else:
        reply = await generate_coach_reply(user.first_name or user.username or "Amigo", text)
        await update.message.reply_text(
            html.escape(reply),
            reply_markup=get_main_reply_keyboard(),
            parse_mode=ParseMode.HTML,
        )


# Alias for compatibility
text_message_handler = process_text_message


