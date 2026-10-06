import asyncio
import logging
import os
import random
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Fallback messages if Gemini API is unreachable or key is not provided
FALLBACK_RESCUE_TEMPLATES = [
    "🦉 ¡{name}! Tu racha de {streak} días está llorando en una esquina. ¿Vas a dejar morir el fuego por {habit}? ¡Entra y sálvala ya! 🔥",
    "🦉 Toc, toc, {name}... Veo que tienes tiempo de ver notificaciones pero no de {habit}. Tu racha de {streak} días corre peligro ⏰⚡",
    "🦉 ¿Sientes ese frío? Es tu racha de {streak} días desvaneciéndose en el abismo. Completa {habits} antes de que sea tarde. 👀🔥",
    "🦉 {name}, tu racha de {streak} días te observa con decepción. 5 minutos bastan para no empezar desde cero mañana. ¡Hazlo! 💥",
]


def _get_fallback_message(username: str, pending_habits: List[str], current_streak: int) -> str:
    """Generate a high-quality dramatic fallback message."""
    template = random.choice(FALLBACK_RESCUE_TEMPLATES)
    first_habit = pending_habits[0] if pending_habits else "tus metas"
    habits_str = ", ".join(pending_habits[:3])
    return template.format(
        name=username or "Amigo",
        streak=current_streak,
        habit=first_habit,
        habits=habits_str,
    )


def _call_gemini_api(username: str, pending_habits: List[str], current_streak: int) -> str:
    """Synchronous worker to call Gemini API via google-genai."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment.")

    client = genai.Client(api_key=api_key)

    habits_str = ", ".join(pending_habits)
    prompt = (
        f"Actúa como un coach de hábitos dramático, divertido y persuasivo al estilo del búho de Duolingo.\n"
        f"Nombre del usuario: {username}\n"
        f"Racha actual: {current_streak} días\n"
        f"Hábitos que todavía NO ha completado hoy: {habits_str}\n\n"
        "Genera un mensaje corto (máx 280 caracteres), persuasivo y divertido/dramático estilo Duolingo "
        "para recordarle al usuario completar sus hábitos. "
        "Haz énfasis en salvar la racha antes de que termine el día. "
        "Devuelve únicamente el texto del mensaje, sin comillas adicionales ni explicaciones."
    )

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )

    text = (response.text or "").strip().strip('"').strip("'")
    if not text:
        raise ValueError("Gemini returned empty response.")
    return text


async def generate_rescue_message(
    username: str,
    pending_habits: List[str],
    current_streak: int,
) -> str:
    """
    Generate a short, persuasive and dramatic Duolingo-style rescue message
    using Google Gemini API with automatic fallback.
    """
    if not pending_habits:
        return f"🎉 ¡Increíble trabajo, {username}! No tienes hábitos pendientes por hoy."

    try:
        # Run sync Gemini SDK call in thread pool to prevent blocking asyncio loop
        message = await asyncio.to_thread(
            _call_gemini_api, username, pending_habits, current_streak
        )
        logger.info(f"Gemini rescue message generated successfully for {username}")
        return message
    except Exception as e:
        logger.warning(
            f"Failed to generate rescue message via Gemini API ({e}). Using dramatic fallback."
        )
        return _get_fallback_message(username, pending_habits, current_streak)
