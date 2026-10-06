from datetime import datetime
import zoneinfo
from typing import Optional


def get_user_today_str(tz_name: Optional[str] = "UTC") -> str:
    """Return current date string (YYYY-MM-DD) for user's timezone."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name or "UTC")
        return datetime.now(tz).strftime("%Y-%m-%d")
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d")


def get_streak_emoji(streak: int) -> str:
    """Return motivational emoji according to streak level (Duolingo style)."""
    if streak == 0:
        return "🌱"
    elif streak < 3:
        return "🔥"
    elif streak < 7:
        return "⚡"
    elif streak < 14:
        return "💥"
    elif streak < 30:
        return "🚀"
    else:
        return "👑"


def get_congratulations_message(streak: int) -> str:
    """Return celebratory message when completing all daily habits."""
    emoji = get_streak_emoji(streak)
    if streak == 1:
        return (
            f"🎉 ¡Primer día completado! {emoji}\n\n"
            "Has encendido tu racha. Mañana vuelve a la misma hora para mantenerla viva."
        )
    elif streak in [3, 7, 14, 21, 30, 50, 100]:
        return (
            f"🏆 ¡HITO ALCANZADO! {streak} DÍAS SEGUIDOS {emoji}\n\n"
            f"¡Eres imparable! Tu constancia está creando hábitos de acero. ¡Sigue así!"
        )
    else:
        return (
            f"🎉 ¡Todos los hábitos de hoy completados! {emoji}\n\n"
            f"Tu racha asciende a **{streak} días** consecutivos. ¡Duolingo estaría orgulloso de ti! 🦉🔥"
        )
