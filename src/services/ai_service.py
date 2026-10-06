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
    "¡Hola, {name}! Sé que el día puede ser ajetreado, pero no olvides {habit}. ¡Aún estás a tiempo de mantener viva tu racha de {streak} días! 💪",
    "¡Ey, {name}! Paso a darte un empujoncito amistoso: todavía tienes pendiente {habit}. Vienes con un gran ritmo de {streak} días, ¡vamos a cuidarlo!",
    "¡Hola, {name}! Tómate unos minutos hoy para {habits}. Llevas {streak} días seguidos y vale la pena el esfuerzo. ¡Tú puedes!",
    "{name}, un recordatorio amigable: completa {habit} antes de descansar para no perder tu racha de {streak} días. ¡Ánimo!",
]

FALLBACK_COACH_REPLIES = [
    "¡Hola, {name}! Qué bueno saludarte. ¿Cómo va tu día? Recuerda que aquí estoy para apoyarte con tus metas.",
    "¡Vamos con todo hoy, {name}! Cada pequeño paso diario cuenta. Si necesitas registrar un nuevo hábito o ver cómo vas, avísame.",
    "¡Ey, {name}! Qué gusto leerte. Puedes ver tu avance en '📋 Mis Hábitos' o contarme qué nuevo hábito tienes en mente.",
    "¡Esa es la actitud, {name}! Cuenta conmigo para mantener la constancia día a día.",
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
    """Synchronous worker to call Gemini API for friendly rescue reminder."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment.")

    client = genai.Client(api_key=api_key)
    habits_str = ", ".join(pending_habits)
    prompt = (
        f"Actúa como un amigo cercano, comprensivo y motivador que acompaña a su compañero en la construcción de hábitos.\n"
        f"Nombre del usuario: {username}\n"
        f"Racha actual: {current_streak} días\n"
        f"Hábitos que todavía tiene pendientes hoy: {habits_str}\n\n"
        "Genera un mensaje corto (máx 240 caracteres), cálido, auténtico y alentador. "
        "Trátalo como a un par, de forma humana y cercana, dándole un empujoncito amigable para que no afloje "
        "y complete sus hábitos antes de finalizar el día. "
        "NO exageres con dramatismo ni amenazas, NO menciones búhos ni mascotas. "
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
    """Generate a friendly, warm reminder message using Gemini API."""
    if not pending_habits:
        return f"🎉 ¡Increíble trabajo, {username}! Ya completaste todos tus hábitos por hoy."

    try:
        return await asyncio.to_thread(_call_gemini_api, username, pending_habits, current_streak)
    except Exception as e:
        logger.warning(f"Failed to generate rescue message via Gemini API ({e}). Using friendly fallback.")
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
Eres el clasificador de intenciones (Intent Router) y motor de NLP de HabitBot, un asistente y compañero amigable de hábitos diarios.
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
   Ejemplos: "mis hábitos", "qué tengo hoy", "cómo voy", "📋 Mis Hábitos", "ver racha", "tablero", "mis metas".
   (datos_habito debe tener todos sus campos en null).
3. "PROBAR_ALERTA": El usuario solicita explícitamente probar, testear o simular la alerta o recordatorio de hábitos.
   Ejemplos: "probar alerta", "haz la alerta", "recordatorio de prueba", "⚡ Probar Alerta", "simular recordatorio".
   (datos_habito debe tener todos sus campos en null).
4. "CREAR_HABITO": El usuario expresa la intención de hacer, construir o agregar un hábito, rutina o meta personal.
   Ejemplos: "Quiero leer 20 min todas las noches a las 22:00", "Tomar 2L de agua", "Salir a correr interdiario", "Meditar 10 min a las 7am", "➕ Agregar Hábito".
   - "titulo": Título limpio, conciso y en infinitivo (máx 50 caracteres). NO incluyas la hora en el título (ej: "Leer 20 min", "Tomar 2L de agua").
   - "frecuencia": "diario", "interdiario", "semanal" (por defecto "diario").
   - "hora": Hora en formato 24h "HH:MM" (ej: "22:00", "07:00"). Si no menciona hora, null.
5. "CONVERSACION_GENERAL": Saludos casuales ("hola", "buenas"), agradecimientos ("gracias"), preguntas sobre cómo funciona o charla general amigable que no active ninguna de las acciones anteriores.
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
        f"Actúa como un amigo cercano, comprensivo y motivador que acompaña a su par en la construcción de hábitos.\n"
        f"Usuario: {username}\n"
        f"Racha actual: {streak} días\n"
        f"Efectividad de cumplimiento semanal: {percentage}%\n"
        f"Hábitos evaluados: {habits_summary}\n\n"
        "Escribe un mensaje de retroalimentación semanal corto (máximo 260 caracteres), auténtico y cálido. "
        "Si el porcentaje es alto (>=80%), felicítalo con alegría genuina y celebra su constancia. "
        "Si es medio (50-79%), reconócele el esfuerzo y anímalo a ir por más la siguiente semana. "
        "Si es bajo (<50%), sé empático, dile que una semana difícil le pasa a cualquiera y anímalo a retomar con calma el lunes. "
        "NO uses tonos agresivos, ni dramatismo de búho, ni amenazas. "
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
            return f"¡Impresionante semana, {username}! Lograste un {percentage}% de efectividad y tu racha de {streak} días está más firme que nunca. ¡A seguir con ese ritmo! 🔥"
        elif percentage >= 50:
            return f"¡Buen trabajo esta semana, {username}! Cerraste con un {percentage}%. Estás construyendo el hábito; la próxima semana vamos por el 100% juntos."
        else:
            return f"Tranquilo, {username}, un {percentage}% significa que tuvimos días complicados, pero cada semana es un nuevo comienzo. ¡El lunes retomamos con fuerza!"


def _call_gemini_coach_reply(username: str, user_text: str) -> str:
    """Generate friendly conversational reply as a supportive companion."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    prompt = (
        f"Eres el compañero y asistente de hábitos de HabitBot. Tu estilo es el de un AMIGO cercano, atento, comprensivo y motivador.\n"
        f"Usuario: {username}\n"
        f"Mensaje del usuario: \"{user_text}\"\n\n"
        "Responde de forma concisa (máximo 160 caracteres), cercana y humana. Trátalo de igual a igual, con calidez. "
        "Invítalo con naturalidad a revisar sus hábitos de hoy o registrar uno nuevo si lo necesita. "
        "NO menciones búhos ni dramatismos. Devuelve únicamente tu respuesta directa."
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
    """Generate conversational reply with friendly companion personality."""
    try:
        return await asyncio.to_thread(_call_gemini_coach_reply, username, user_text)
    except Exception:
        template = random.choice(FALLBACK_COACH_REPLIES)
        return template.format(name=username or "Amigo")
