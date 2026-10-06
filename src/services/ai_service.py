import asyncio
import json
import logging
import os
import random
import re
from typing import List, Optional, Dict, Any
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

    for model_name in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = (response.text or "").strip().strip('"').strip("'")
            if text:
                return text
        except Exception as e:
            logger.warning(f"Gemini rescue attempt with {model_name} failed: {e}")
            continue

    raise ValueError("All Gemini model attempts failed.")


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


def _heuristic_parse_habit_intent(user_text: str) -> Dict[str, Any]:
    """Smart fallback parser if Gemini API is unreachable."""
    clean = user_text.strip()
    hour = None
    time_match = re.search(r'(?:a las|a la|alas)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', clean, re.I)
    if time_match:
        h = int(time_match.group(1))
        m = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3).lower() if time_match.group(3) else None
        if ampm == "pm" and h < 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            hour = f"{h:02d}:{m:02d}"

    freq = "diario"
    if re.search(r'interdiario|cada dos d[ií]as', clean, re.I):
        freq = "interdiario"
    elif re.search(r'semanal|cada semana|fines de semana', clean, re.I):
        freq = "semanal"

    habit_pattern = (
        r'leer|tomar|beber|agua|correr|caminar|ejercicio|entrenar|flexiones|gimnasio|'
        r'meditar|estudiar|dormir|despertar|escribir|programar|orar|rezar|dieta|comer|libro'
    )
    is_habit = bool(re.search(habit_pattern, clean, re.I))

    title = clean
    for prefix in [
        r'^(?:hola[,\.\s]+)?(?:quiero|voy\s+a|deseo|me\s+gustar[ií]a|mi\s+meta\s+es|'
        r'agregar(?:\s+h[aá]bito)?|anotar|poner|crear|empezar\s+a)\s+'
    ]:
        title = re.sub(prefix, '', title, flags=re.I)
    if time_match:
        title = re.sub(r'(?:a las|a la|alas)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?', '', title, flags=re.I)
    title = re.sub(r'\s+', ' ', title).strip()

    if is_habit and len(title) >= 3:
        return {
            "es_habito": True,
            "titulo": title[0].upper() + title[1:],
            "frecuencia": freq,
            "hora": hour,
        }
    return {
        "es_habito": False,
        "titulo": "",
        "frecuencia": "diario",
        "hora": None,
    }


def _call_gemini_parse_intent(user_text: str) -> Dict[str, Any]:
    """Synchronous worker to parse natural language habit intent into JSON schema."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _heuristic_parse_habit_intent(user_text)

    client = genai.Client(api_key=api_key)
    prompt = f"""
Eres el motor de Inteligencia Artificial y NLP de HabitBot.
Analiza el siguiente texto de un usuario y responde estrictamente con un JSON válido con este esquema exacto:
{{
  "es_habito": boolean,
  "titulo": string,
  "frecuencia": "diario" | "interdiario" | "dias_especificos" | "semanal",
  "hora": string | null
}}

Instrucciones:
1. "es_habito": true si el usuario intenta crear, registrar o definir un hábito, rutina o meta diaria/recurrente.
2. "titulo": Nombre del hábito sanitizado, limpio y en infinitivo (máx 50 caracteres). NO incluyas la hora en el título.
   Ejemplos: "Leer 20 min", "Tomar 2L de agua", "Salir a correr", "Hacer 30 flexiones", "Meditar 10 min".
3. "frecuencia": "diario", "interdiario", "dias_especificos" o "semanal" (por defecto "diario").
4. "hora": Extrae la hora mencionada en formato 24h "HH:MM" (ej: "07:00", "22:00", "20:30", "14:00").
   Si el usuario NO menciona ninguna hora específica, asigna null.
5. Si el mensaje NO es un hábito (por ejemplo saludos casuales "hola", preguntas, agradecimientos "gracias", o comentarios irrelevantes):
   devuelve {{"es_habito": false, "titulo": "", "frecuencia": "diario", "hora": null}}

Texto del usuario: "{user_text}"
"""

    for model_name in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            raw = (response.text or "").strip()
            data = json.loads(raw)
            # Ensure correct keys and types
            return {
                "es_habito": bool(data.get("es_habito", False)),
                "titulo": str(data.get("titulo", "")).strip(),
                "frecuencia": str(data.get("frecuencia", "diario")).strip(),
                "hora": str(data["hora"]).strip() if data.get("hora") else None,
            }
        except Exception as e:
            logger.warning(f"Model {model_name} failed parsing habit intent: {e}")
            continue

    return _heuristic_parse_habit_intent(user_text)


async def parse_habit_intent(user_text: str) -> Dict[str, Any]:
    """
    Parse free-form user message using Gemini API to extract structured habit intent.
    Returns:
    {
        "es_habito": bool,
        "titulo": str,
        "frecuencia": str,
        "hora": Optional[str]  # e.g. "22:00" or None
    }
    """
    if not user_text or len(user_text.strip()) < 2:
        return {"es_habito": False, "titulo": "", "frecuencia": "diario", "hora": None}

    try:
        return await asyncio.to_thread(_call_gemini_parse_intent, user_text)
    except Exception as e:
        logger.warning(f"Error in parse_habit_intent: {e}")
        return _heuristic_parse_habit_intent(user_text)


# Backwards compatibility helper
async def extract_habit_from_text(user_message: str) -> Optional[str]:
    """Extract habit title from natural language text."""
    res = await parse_habit_intent(user_message)
    if res.get("es_habito") and res.get("titulo"):
        return res["titulo"]
    return None
