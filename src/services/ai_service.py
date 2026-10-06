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

# Fallback templates if Gemini API is temporarily unavailable
FALLBACK_RESCUE_TEMPLATES = [
    "🦉 ¡{name}! Tu racha de {streak} días está llorando en una esquina. ¿Vas a dejar morir el fuego por {habit}? ¡Entra y sálvala ya! 🔥",
    "🦉 Toc, toc, {name}... Veo que tienes tiempo de ver notificaciones pero no de {habit}. Tu racha de {streak} días corre peligro ⏰⚡",
    "🦉 ¿Sientes ese frío? Es tu racha de {streak} días desvaneciéndose en el abismo. Completa {habits} antes de que sea tarde. 👀🔥",
    "🦉 {name}, tu racha de {streak} días te observa con decepción. 5 minutos bastan para no empezar desde cero mañana. ¡Hazlo! 💥",
]

FALLBACK_COACH_REPLIES = [
    "🦉 ¡Hola, {name}! Aquí estoy vigilando que mantengas viva esa racha. ¿Qué hábito vamos a conquistar hoy? 🔥",
    "🦉 Menos charla y más acción, {name}. Recuerda que cada día que no completas tus hábitos, un búho llora. 👀",
    "🦉 ¡Te tengo en la mira, {name}! Mantén la disciplina y tu racha será legendaria. Toca '📋 Mis Hábitos' para ver tu avance.",
    "🦉 ¡Esa es la actitud! Recuerda que puedes decirme directamente tus nuevos hábitos (ej: 'Quiero leer 20 min a las 22:00'). 🎯",
]


def _get_fallback_message(username: str, pending_habits: List[str], current_streak: int) -> str:
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
    """Synchronous worker to call Gemini API for rescue alert."""
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
        "para recordarle al usuario completar sus hábitos antes de que termine el día. "
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
    """Generate a dramatic Duolingo-style rescue message using Gemini API."""
    if not pending_habits:
        return f"🎉 ¡Increíble trabajo, {username}! No tienes hábitos pendientes por hoy."

    try:
        return await asyncio.to_thread(_call_gemini_api, username, pending_habits, current_streak)
    except Exception as e:
        logger.warning(f"Failed to generate rescue message via Gemini API ({e}). Using dramatic fallback.")
        return _get_fallback_message(username, pending_habits, current_streak)


def _heuristic_classify_intent(user_text: str) -> Dict[str, Any]:
    """Smart heuristic fallback to classify intent if Gemini API is unavailable."""
    clean = user_text.strip().lower()

    # 1. VER_REPORTE
    report_keywords = [
        "reporte", "semana", "resumen", "estadisticas", "estadísticas",
        "metricas", "métricas", "rendimiento", "mi semana", "como me fue", "¿cómo me fue"
    ]
    if any(k in clean for k in report_keywords):
        return {
            "intencion": "VER_REPORTE",
            "datos_habito": {"titulo": None, "frecuencia": None, "hora": None},
        }

    # 2. PROBAR_ALERTA
    alert_keywords = ["probar alerta", "alerta duolingo", "simular alerta", "rescate", "haz la alerta"]
    if any(k in clean for k in alert_keywords):
        return {
            "intencion": "PROBAR_ALERTA",
            "datos_habito": {"titulo": None, "frecuencia": None, "hora": None},
        }

    # 3. VER_ESTADO
    status_keywords = [
        "mis hábitos", "mis habitos", "hoy", "racha", "ver racha",
        "tablero", "que tengo", "qué tengo", "estado"
    ]
    if any(k in clean for k in status_keywords) and not any(k in clean for k in ["quiero", "nuevo", "agregar"]):
        return {
            "intencion": "VER_ESTADO",
            "datos_habito": {"titulo": None, "frecuencia": None, "hora": None},
        }

    # 4. CREAR_HABITO
    time_match = re.search(r'(?:a las|a la|alas)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', user_text, re.I)
    hour = None
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

    habit_pattern = (
        r'leer|tomar|beber|agua|correr|caminar|ejercicio|entrenar|flexiones|gimnasio|'
        r'meditar|estudiar|dormir|despertar|escribir|programar|orar|rezar|dieta|comer|libro|'
        r'quiero|voy\s+a|deseo|me\s+gustar[ií]a|agregar|meta'
    )
    if re.search(habit_pattern, clean):
        title = user_text.strip()
        for prefix in [
            r'^(?:hola[,\.\s]+)?(?:quiero|voy\s+a|deseo|me\s+gustar[ií]a|mi\s+meta\s+es|'
            r'agregar(?:\s+h[aá]bito)?|anotar|poner|crear|empezar\s+a)\s+'
        ]:
            title = re.sub(prefix, '', title, flags=re.I)
        if time_match:
            title = re.sub(r'(?:a las|a la|alas)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?', '', title, flags=re.I)
        title = re.sub(r'\s+', ' ', title).strip()

        if len(title) >= 3:
            return {
                "intencion": "CREAR_HABITO",
                "datos_habito": {
                    "titulo": title[0].upper() + title[1:],
                    "frecuencia": "diario",
                    "hora": hour,
                },
            }

    # 5. CONVERSACION_GENERAL
    return {
        "intencion": "CONVERSACION_GENERAL",
        "datos_habito": {"titulo": None, "frecuencia": None, "hora": None},
    }


def _call_gemini_intent_router(user_text: str) -> Dict[str, Any]:
    """Synchronous worker to classify intent using Gemini API."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _heuristic_classify_intent(user_text)

    client = genai.Client(api_key=api_key)
    prompt = f"""
Eres el clasificador de intenciones (Intent Router) y motor de NLP de HabitBot (Coach de hábitos estilo Duolingo).
Analiza el mensaje del usuario y responde ESTRICTAMENTE con un objeto JSON válido con esta estructura:
{{
  "intencion": "CREAR_HABITO" | "VER_REPORTE" | "VER_ESTADO" | "PROBAR_ALERTA" | "CONVERSACION_GENERAL",
  "datos_habito": {{
    "titulo": string | null,
    "frecuencia": string | null,
    "hora": string | null
  }}
}}

Criterios de clasificación:
1. "VER_REPORTE": El usuario pide su desempeño semanal, resumen, reporte, métricas o estadísticas de la semana.
   Ejemplos: "¿cómo me fue esta semana?", "dame mi resumen", "métricas de la semana", "reporte semanal", "📊 Mi Semana", "estadísticas".
   (datos_habito debe tener todos sus campos en null).
2. "VER_ESTADO": El usuario desea ver sus hábitos del día, progreso actual o racha.
   Ejemplos: "mis hábitos", "qué tengo hoy", "cómo voy", "📋 Mis Hábitos", "ver racha", "tablero".
   (datos_habito debe tener todos sus campos en null).
3. "PROBAR_ALERTA": El usuario solicita explícitamente probar, testear o simular la alerta de rescate Duolingo.
   Ejemplos: "probar alerta", "haz la alerta", "alerta duolingo", "⚡ Probar Alerta", "simular rescate".
   (datos_habito debe tener todos sus campos en null).
4. "CREAR_HABITO": El usuario expresa la intención de hacer, construir o agregar un hábito, rutina o meta personal.
   Ejemplos: "Quiero leer 20 min todas las noches a las 22:00", "Tomar 2L de agua", "Salir a correr interdiario", "Meditar 10 min a las 7am", "➕ Agregar Hábito".
   - "titulo": Título limpio, conciso y en infinitivo (máx 50 caracteres). NO incluyas la hora en el título. (ej: "Leer 20 min", "Tomar 2L de agua").
   - "frecuencia": "diario", "interdiario", "semanal" (por defecto "diario").
   - "hora": Hora en formato 24h "HH:MM" (ej: "22:00", "07:00"). Si no menciona hora, null.
5. "CONVERSACION_GENERAL": Saludos casuales ("hola", "buenas"), bromas, agradecimientos ("gracias"), preguntas casuales ("quién eres") o charla general que no active ninguna de las acciones anteriores.
   (datos_habito debe tener todos sus campos en null).

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
            intencion = data.get("intencion", "CONVERSACION_GENERAL")
            datos = data.get("datos_habito") or {}
            return {
                "intencion": intencion,
                "datos_habito": {
                    "titulo": str(datos["titulo"]).strip() if datos.get("titulo") else None,
                    "frecuencia": str(datos["frecuencia"]).strip() if datos.get("frecuencia") else "diario",
                    "hora": str(datos["hora"]).strip() if datos.get("hora") else None,
                },
            }
        except Exception as e:
            logger.warning(f"Model {model_name} failed classifying intent: {e}")
            continue

    return _heuristic_classify_intent(user_text)


async def classify_and_parse_intent(user_text: str) -> Dict[str, Any]:
    """
    Classify user message intent and parse habit data if present.
    Returns:
    {
        "intencion": "CREAR_HABITO" | "VER_REPORTE" | "VER_ESTADO" | "PROBAR_ALERTA" | "CONVERSACION_GENERAL",
        "datos_habito": {
            "titulo": Optional[str],
            "frecuencia": Optional[str],
            "hora": Optional[str]
        }
    }
    """
    if not user_text or len(user_text.strip()) == 0:
        return {
            "intencion": "CONVERSACION_GENERAL",
            "datos_habito": {"titulo": None, "frecuencia": None, "hora": None},
        }

    try:
        return await asyncio.to_thread(_call_gemini_intent_router, user_text)
    except Exception as e:
        logger.warning(f"Error in classify_and_parse_intent: {e}")
        return _heuristic_classify_intent(user_text)


# Backwards compatibility helper
async def parse_habit_intent(user_text: str) -> Dict[str, Any]:
    """Parse habit intent (compatibility helper)."""
    res = await classify_and_parse_intent(user_text)
    is_habit = res["intencion"] == "CREAR_HABITO"
    datos = res.get("datos_habito", {})
    return {
        "es_habito": is_habit,
        "titulo": datos.get("titulo") or "",
        "frecuencia": datos.get("frecuencia") or "diario",
        "hora": datos.get("hora"),
    }


async def extract_habit_from_text(user_text: str) -> Optional[str]:
    """Extract habit title from natural language text (compatibility helper)."""
    res = await parse_habit_intent(user_text)
    if res.get("es_habito") and res.get("titulo"):
        return res["titulo"]
    return None


def _call_gemini_weekly_feedback(username: str, streak: int, percentage: int, habits_summary: str) -> str:
    """Generate weekly review feedback with Gemini API."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    prompt = (
        f"Actúa como un coach de hábitos motivacional, divertido y ligeramente sarcástico estilo Duolingo.\n"
        f"Usuario: {username}\n"
        f"Racha actual: {streak} días\n"
        f"Efectividad de cumplimiento semanal: {percentage}%\n"
        f"Hábitos evaluados: {habits_summary}\n\n"
        "Escribe un mensaje de retroalimentación semanal corto (máximo 280 caracteres). "
        "Si el porcentaje es alto (>=80%), felicítalo con energía. Si es medio (50-79%), motívalo a no aflojar. "
        "Si es bajo (<50%), usa el humor dramático del búho de Duolingo para exigirle que despierte la próxima semana. "
        "Devuelve únicamente el texto directo, sin comillas ni explicaciones."
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
            continue

    raise ValueError("Gemini weekly feedback failed.")


async def generate_weekly_feedback(
    username: str,
    streak: int,
    percentage: int,
    habits_summary: str = "",
) -> str:
    """Generate personalized weekly feedback using Gemini API with fallback."""
    try:
        return await asyncio.to_thread(
            _call_gemini_weekly_feedback, username, streak, percentage, habits_summary
        )
    except Exception as e:
        logger.warning(f"Failed to generate weekly feedback with Gemini ({e}). Using fallback.")
        if percentage >= 80:
            return f"🦉 ¡Impresionante semana, {username}! {percentage}% de efectividad. ¡Esa racha de {streak} días es imparable! 🔥🏆"
        elif percentage >= 50:
            return f"🦉 ¡Buen esfuerzo, {username}! Lograste un {percentage}%, pero la próxima semana queremos el 100%. ¡A cuidar esa racha! ⚡"
        else:
            return f"🦉 ¡Alerta, {username}! Solo un {percentage}% esta semana. El búho está llorando lágrimas de fuego. ¡La próxima semana renacemos! 😭🔥"


def _call_gemini_coach_reply(username: str, user_text: str) -> str:
    """Generate quick coach conversational reply."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    prompt = (
        f"Eres el búho coach de hábitos de HabitBot (estilo Duolingo: motivador, gracioso y un poco dramático con la disciplina).\n"
        f"Usuario: {username}\n"
        f"Mensaje del usuario: \"{user_text}\"\n\n"
        "Responde de forma muy concisa (máximo 160 caracteres). Invítalo con humor a revisar sus hábitos o registrar uno nuevo si lo desea. "
        "Devuelve únicamente tu respuesta directa."
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
        except Exception:
            continue

    raise ValueError("Gemini coach reply failed.")


async def generate_coach_reply(username: str, user_text: str) -> str:
    """Generate conversational reply with Duolingo coach personality."""
    try:
        return await asyncio.to_thread(_call_gemini_coach_reply, username, user_text)
    except Exception:
        template = random.choice(FALLBACK_COACH_REPLIES)
        return template.format(name=username or "Amigo")
