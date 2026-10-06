# 🦉 HabitBot

> **Un Coach de Hábitos en Telegram al estilo Duolingo.**  
> HabitBot te ayuda a crear, monitorear y mantener hábitos diarios mediante recordatorios inteligentes, seguimiento de rachas y motivación personalizada potenciada por la API de Google Gemini.

---

## 🚀 Características Principales

- **Gestión de Hábitos:** Crea y gestiona hábitos con metas y frecuencias personalizadas.
- **Rachas y Gamificación:** Mecánicas al estilo Duolingo para proteger y celebrar tus rachas diarias.
- **Notificaciones Proactivas:** Recordatorios matutinos y avisos de racha en peligro mediante APScheduler.
- **Coach IA con Gemini:** Retroalimentación inteligente y mensajes motivacionales dinámicos adaptados a tu progreso.
- **Persistencia Asíncrona:** Base de datos SQLite optimizada con `aiosqlite`.

---

## 📁 Estructura del Proyecto

```text
habit_Bot/
├── src/
│   ├── bot/          # Handlers de Telegram (comandos, callbacks, menús)
│   ├── core/         # Lógica de negocio (gestión de hábitos, cálculo de rachas)
│   ├── database/     # Modelos, conexión y consultas con aiosqlite
│   ├── scheduler/    # Tareas programadas y motor de alertas Duolingo
│   └── services/     # Integración con Google GenAI (Gemini API)
├── .env.example      # Plantilla de variables de entorno
├── .gitignore        # Exclusiones de Git (entornos, logs, base de datos)
├── main.py           # Punto de entrada de la aplicación
├── requirements.txt  # Dependencias del proyecto
└── README.md         # Documentación del proyecto
```

---

## 🗄️ Esquema de Base de Datos

SQLite gestionado asíncronamente con las siguientes tablas:

### 1. `users`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Telegram User ID |
| `username` | TEXT | Nombre de usuario de Telegram |
| `timezone` | TEXT | Zona horaria del usuario (default: `'UTC'`) |
| `morning_hour` | TEXT | Hora preferida para el resumen matutino (default: `'08:00'`) |
| `streak_count` | INTEGER | Días consecutivos de racha activa (default: `0`) |
| `last_completed_date` | TEXT | Fecha del último hábito completado (`YYYY-MM-DD`) |
| `created_at` | TIMESTAMP | Fecha de registro |

### 2. `habits`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Identificador único del hábito |
| `user_id` | INTEGER | Clave foránea referenciando a `users.id` |
| `title` | TEXT | Título o descripción del hábito |
| `frequency` | TEXT | Frecuencia de ejecución (default: `'daily'`) |
| `created_at` | TIMESTAMP | Fecha de creación del hábito |

### 3. `daily_logs`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Identificador único del registro |
| `habit_id` | INTEGER | Clave foránea referenciando a `habits.id` |
| `user_id` | INTEGER | Clave foránea referenciando a `users.id` |
| `date` | TEXT | Fecha del registro (`YYYY-MM-DD`) |
| `completed` | BOOLEAN | Estado de cumplimiento (`0` o `1`) |
| `checked_at` | TIMESTAMP | Marca temporal de la confirmación |

---

## 🛠️ Instalación y Configuración

### 1. Prerrequisitos
- Python 3.10 o superior (compatible con Python 3.13)
- Token de Bot de Telegram (obtenido a través de [@BotFather](https://t.me/BotFather))
- API Key de Google Gemini ([Google AI Studio](https://aistudio.google.com/))

### 2. Clonar el Repositorio
```bash
git clone https://github.com/leonardobaca7/habit_Bot.git
cd habit_Bot
```

### 3. Configurar Entorno Virtual
En Windows (PowerShell):
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 5. Configurar Variables de Entorno
Copia el archivo `.env.example` a `.env` y completa tus credenciales:
```bash
cp .env.example .env
```
Edita `.env`:
```env
TELEGRAM_BOT_TOKEN="tu_token_aqui"
GEMINI_API_KEY="tu_api_key_aqui"
DATABASE_PATH="habitbot.db"
```

---

## ▶️ Ejecución y Pruebas

Para verificar la inicialización de la base de datos y arrancar el bot:
```bash
python main.py
```

Para correr las pruebas de verificación de la base de datos:
```bash
python -m src.database.db
```
