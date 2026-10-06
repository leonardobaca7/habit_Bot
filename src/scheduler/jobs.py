import html
import logging
from datetime import datetime
import zoneinfo
from typing import Optional, List, Dict, Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from src.database.queries import (
    get_all_users,
    get_user,
    get_user_habits,
    get_today_habits_status,
    has_notification_been_sent,
    record_notification_sent,
    get_weekly_statistics,
)
from src.core.streaks import get_user_today_str, get_streak_emoji
from src.core.habits import format_status_message, build_status_keyboard
from src.services.ai_service import generate_rescue_message, generate_weekly_feedback

logger = logging.getLogger(__name__)


def calculate_rescue_hour(morning_hour: str, offset_hours: float = 6.5) -> str:
    """Calculate the rescue notification hour based on morning_hour + offset."""
    try:
        parts = morning_hour.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        total_mins = h * 60 + m + int(offset_hours * 60)
        norm_mins = total_mins % (24 * 60)
        return f"{norm_mins // 60:02d}:{norm_mins % 60:02d}"
    except Exception:
        return "14:30"


async def send_morning_notification(bot: Bot, user: Dict[str, Any], force: bool = False) -> bool:
    """
    Send daily morning notification with the user's habits and interactive buttons.
    """
    user_id = user["id"]
    tz = user.get("timezone", "UTC")
    today_str = get_user_today_str(tz)

    if not force and await has_notification_been_sent(user_id, today_str, "morning"):
        return False

    habits = await get_today_habits_status(user_id, today_str)
    if not habits:
        logger.info(f"User {user_id} has no habits configured; skipping morning notification.")
        return False

    name = html.escape(user.get("username") or "Campeón")
    streak = user.get("streak_count", 0)
    emoji = get_streak_emoji(streak)

    header = (
        f"🌅 <b>¡Buenos días, {name}!</b> {emoji}\n"
        "Comienza tu día sumando a tu racha. Aquí tienes tus hábitos para hoy:\n\n"
    )
    body = format_status_message(habits, streak, today_str)
    full_message = header + body
    keyboard = build_status_keyboard(habits)

    try:
        await bot.send_message(
            chat_id=user_id,
            text=full_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        await record_notification_sent(user_id, today_str, "morning")
        logger.info(f"Morning notification successfully sent to user {user_id}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to send morning notification to user {user_id}: {e}")
        return False


async def send_rescue_notification(bot: Bot, user: Dict[str, Any], force: bool = False) -> bool:
    """
    Send Duolingo-style rescue notification if user has pending habits after 6.5h.
    Uses Gemini API to generate an urgent, persuasive reminder.
    """
    user_id = user["id"]
    tz = user.get("timezone", "UTC")
    today_str = get_user_today_str(tz)

    if not force and await has_notification_been_sent(user_id, today_str, "rescue"):
        return False

    habits = await get_today_habits_status(user_id, today_str)
    if not habits:
        return False

    pending_habits = [h["title"] for h in habits if not h.get("completed")]
    if not pending_habits:
        logger.info(f"User {user_id} has already completed all habits; no rescue needed.")
        return False

    name = user.get("username") or "Amigo"
    streak = user.get("streak_count", 0)

    # 1. Generate dramatic message via Gemini API
    ai_message = await generate_rescue_message(
        username=name,
        pending_habits=pending_habits,
        current_streak=streak,
    )

    safe_ai_message = html.escape(ai_message)
    full_message = (
        "⏰ <b>¡Recordatorio de Racha!</b> 🔥\n\n"
        f"{safe_ai_message}\n\n"
        "👇 <i>Toca para marcar tu avance de hoy:</i>"
    )
    keyboard = build_status_keyboard(habits)

    try:
        await bot.send_message(
            chat_id=user_id,
            text=full_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        await record_notification_sent(user_id, today_str, "rescue")
        logger.info(f"Rescue notification successfully sent to user {user_id}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to send rescue notification to user {user_id}: {e}")
        return False


async def send_habit_custom_notification(bot: Bot, user: Dict[str, Any], habit: Dict[str, Any]) -> bool:
    """Send reminder for a specific habit when its custom hour arrives."""
    user_id = user["id"]
    tz = user.get("timezone", "UTC")
    today_str = get_user_today_str(tz)
    notif_key = f"habit_{habit['id']}"

    if await has_notification_been_sent(user_id, today_str, notif_key):
        return False

    status_list = await get_today_habits_status(user_id, today_str)
    for h in status_list:
        if h["habit_id"] == habit["id"] and h.get("completed"):
            return False

    safe_title = html.escape(habit["title"])
    message = (
        f"⏰ <b>¡Momento de tu hábito!</b> 🎯\n\n"
        f"📌 <b>{safe_title}</b>\n\n"
        "Un pequeño paso hoy protege tu racha. ¡Hazlo ahora!"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Marcar {habit['title'][:20]}", callback_data=f"toggle_{habit['id']}")],
        [InlineKeyboardButton("📋 Ver Todos los Hábitos", callback_data="status_refresh")],
    ])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        await record_notification_sent(user_id, today_str, notif_key)
        logger.info(f"Custom habit notification sent for habit {habit['id']} to user {user_id}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to send custom habit notification: {e}")
        return False


async def send_weekly_report(bot: Bot, user: Dict[str, Any], force: bool = False) -> bool:
    """
    Generate and send the 7-day habit completion weekly report.
    Scheduled for Sundays at 20:00 (local user time) or triggered via /test_weekly.
    """
    user_id = user["id"]
    tz = user.get("timezone", "UTC")
    today_str = get_user_today_str(tz)

    if not force and await has_notification_been_sent(user_id, today_str, "weekly_report"):
        return False

    stats = await get_weekly_statistics(user_id, today_str)
    if stats["total_habits"] == 0:
        if force:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🌱 <b>No tienes hábitos activos</b> para evaluar en tu reporte semanal.\n\n"
                        "¡Agrega tu primer hábito escribiéndolo o con <b>➕ Agregar Hábito</b>!"
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError as e:
                logger.error(f"Error sending empty weekly report to user {user_id}: {e}")
        return False

    name = user.get("username") or "Campeón"
    streak = user.get("streak_count", 0)
    pct = stats["percentage"]

    # Habit summary string for AI feedback
    habits_summary = ", ".join([
        f"{h['title']} ({h['completed_days']}/7 días)"
        for h in stats["habit_breakdown"]
    ])

    # Generate motivational/Duolingo feedback with Gemini API
    ai_feedback = await generate_weekly_feedback(
        username=name,
        streak=streak,
        percentage=pct,
        habits_summary=habits_summary,
    )

    safe_name = html.escape(name)
    safe_feedback = html.escape(ai_feedback)
    emoji = get_streak_emoji(streak)

    lines = [
        "📊 <b>¡Reporte Semanal de Hábitos!</b>\n",
        f"👤 <b>Atleta de la constancia:</b> {safe_name}",
        f"📅 <b>Periodo:</b> {stats['start_date']} al {stats['end_date']}",
        f"🔥 <b>Racha actual:</b> {streak} días {emoji}",
        f"🎯 <b>Cumplimiento esta semana:</b> {pct}% ({stats['completed_count']}/{stats['total_expected']} check-ins)\n",
        "📋 <b>Desglose por hábito:</b>",
    ]

    for h in stats["habit_breakdown"]:
        days = h["completed_days"]
        bar = "🟩" * days + "⬜" * (7 - days)
        lines.append(f"• <b>{html.escape(h['title'])}</b>: {days}/7 días\n  [{bar}]")

    lines.append(f"\n💬 <b>Comentario de tu Compañero:</b>\n<i>\"{safe_feedback}\"</i>")

    full_message = "\n".join(lines)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Ver Tablero de Hoy", callback_data="status_refresh")]
    ])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=full_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        if not force:
            await record_notification_sent(user_id, today_str, "weekly_report")
        logger.info(f"Weekly report successfully sent to user {user_id}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to send weekly report to user {user_id}: {e}")
        return False


async def dispatch_scheduled_notifications(bot: Bot) -> None:
    """
    Periodic job to inspect users and dispatch morning & rescue notifications
    at their respective configured hours, custom habit notifications,
    and Sunday weekly reports.
    """
    try:
        users = await get_all_users()
        for user in users:
            tz_str = user.get("timezone", "UTC")
            try:
                user_tz = zoneinfo.ZoneInfo(tz_str)
                now_user = datetime.now(user_tz)
            except Exception:
                now_user = datetime.utcnow()

            current_hm = now_user.strftime("%H:%M")
            morning_hour = user.get("morning_hour", "08:00")
            rescue_hour = calculate_rescue_hour(morning_hour, offset_hours=6.5)

            # 1. Check Morning Hour
            if current_hm == morning_hour:
                await send_morning_notification(bot, user, force=False)

            # 2. Check Rescue Hour (6.5 hours later)
            elif current_hm == rescue_hour:
                await send_rescue_notification(bot, user, force=False)

            # 3. Check Custom Habit Hours
            habits = await get_user_habits(user["id"])
            for h in habits:
                if h.get("time") and h["time"] == current_hm:
                    await send_habit_custom_notification(bot, user, h)

            # 4. Check Weekly Report (Sundays at 20:00)
            if now_user.weekday() == 6 and current_hm == "20:00":
                await send_weekly_report(bot, user, force=False)

    except Exception as e:
        logger.error(f"Error in notification dispatcher: {e}", exc_info=True)


async def _job_wrapper(context: ContextTypes.DEFAULT_TYPE) -> None:
    """APScheduler repeating job callback executed by telegram.ext.JobQueue."""
    await dispatch_scheduled_notifications(context.bot)


def setup_scheduler(application: Application) -> None:
    """
    Configure and register the APScheduler repeating dispatcher
    with the Telegram Application JobQueue.
    """
    job_queue = application.job_queue
    if not job_queue:
        logger.warning("JobQueue is not available on this Application instance.")
        return

    # Run every 60 seconds to evaluate user morning and rescue schedules
    job_queue.run_repeating(
        _job_wrapper,
        interval=60,
        first=10,
        name="habitbot_notification_dispatcher",
    )
    logger.info("APScheduler repeating notification dispatcher configured (every 60s).")
