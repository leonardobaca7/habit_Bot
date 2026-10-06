# 🦉 HabitBot — Coach Inteligente de Hábitos en Telegram

> **Un Coach de Hábitos en Telegram al estilo Duolingo con Inteligencia Artificial.**  
> HabitBot te ayuda a crear, monitorear y sostener hábitos diarios mediante recordatorios proactivos, seguimiento gamificado de rachas y procesamiento de lenguaje natural (NLP) potenciado por la API de Google Gemini.

---

## 🚀 Características Principales

- **🧠 Enrutador de Intenciones por IA (Gemini NLP):** Olvídate de comandos rígidos. Puedes escribir en lenguaje totalmente natural (ej: *"Quiero leer 20 min a las 22:00"*, *"¿cómo me fue esta semana?"*, *"probar alerta"*) y Gemini clasificará la intención y extraerá los datos en formato JSON estructurado.
- **🔥 Rachas y Gamificación:** Contador diario de días consecutivos con emojis evolutivos (🌱 ➡️ 🥉 ➡️ 🥈 ➡️ 🥇 ➡️ 👑 ➡️ ⚡ ➡️ 🌟).
- **📋 Tablero Interactivo:** Mensajes con casillas de verificación en vivo (`[⬜]` / `[✅]`) actualizables en tiempo real mediante *Inline Keyboards*.
- **⌨️ Teclado Persistente (ReplyKeyboard):** Acceso rápido con 4 botones esenciales:
  - `📋 Mis Hábitos`
  - `📊 Mi Semana`
  - `➕ Agregar Hábito`
  - `⚡ Probar Alerta`
- **⏰ Notificaciones Proactivas (APScheduler):**
  - **Notificación Matutina:** Resumen matutino interactivo con los hábitos de la jornada.
  - **Notificación de Rescate (Regla 6.5h):** Alerta push dramática y divertida estilo Duolingo redactada por Gemini cuando quedan hábitos pendientes.
  - **Recordatorios por Horario Específico:** Alertas automáticas cuando llega la hora programada de cada hábito.
  - **Reporte Semanal de los Domingos:** Todos los domingos a las 20:00 (hora local del usuario), calcula las estadísticas de los últimos 7 días y genera una retroalimentación motivacional personalizada con IA.
- **🛠️ Comandos de Depuración Inmediata:** Comandos `/test_duolingo`, `/test_weekly` y `/test_morning` para verificar las respuestas de IA y cálculos de base de datos sin esperas.

---

## 📁 Arquitectura del Proyecto

```text
habit_Bot/
├── src/
│   ├── bot/                 # Interfaz de Telegram (python-telegram-bot)
│   │   ├── handlers.py      # Enrutador central de intenciones, comandos y callbacks
│   │   └── __init__.py
│   ├── core/                # Lógica de negocio y gamificación
│   │   ├── habits.py        # Formateo de tableros, listas y teclados interactivos
│   │   ├── streaks.py       # Cálculo de rachas, días consecutivos y felicitaciones
│   │   └── __init__.py
│   ├── database/            # Capa de datos asíncrona (aiosqlite)
│   │   ├── db.py            # Inicialización de esquema y migraciones automáticas
│   │   ├── queries.py       # Consultas SQL (usuarios, hábitos, logs, métricas 7 días)
│   │   └── __init__.py
│   ├── scheduler/           # Motor de tareas en segundo plano (APScheduler)
│   │   ├── jobs.py          # Despachador de alertas, cálculo de horas y reporte semanal
│   │   └── __init__.py
│   └── services/            # Integración de Inteligencia Artificial (Google Gemini)
│       ├── ai_service.py    # Clasificador de intenciones, alertas dramáticas y feedback
│       └── __init__.py
├── .env.example             # Plantilla de variables de entorno
├── .gitignore               # Exclusiones de Git (entornos, logs, base de datos)
├── main.py                  # Punto de entrada de la aplicación y configuración de polling
├── requirements.txt         # Dependencias del proyecto
└── README.md                # Documentación técnica completa
```

---

## 🗄️ Esquema de la Base de Datos SQLite

Gestionado asíncronamente con `aiosqlite` en `habitbot.db`:

### 1. `users`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Telegram User ID |
| `username` | TEXT | Nombre de usuario o primer nombre |
| `timezone` | TEXT | Zona horaria del usuario (default: `'UTC'`) |
| `morning_hour` | TEXT | Hora del resumen diario (default: `'08:00'`) |
| `streak_count` | INTEGER | Días consecutivos completados (default: `0`) |
| `last_completed_date` | TEXT | Fecha del último día completado (`YYYY-MM-DD`) |
| `created_at` | TIMESTAMP | Fecha de registro |

### 2. `habits`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | ID único del hábito |
| `user_id` | INTEGER | Clave foránea referenciando a `users.id` |
| `title` | TEXT | Título o descripción del hábito |
| `frequency` | TEXT | Frecuencia de ejecución (`'diario'`, etc.) |
| `time` | TEXT | Hora programada del hábito (`"HH:MM"`) |
| `created_at` | TIMESTAMP | Fecha de creación del hábito |

### 3. `daily_logs`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | ID único del check-in |
| `habit_id` | INTEGER | Clave foránea referenciando a `habits.id` |
| `user_id` | INTEGER | Clave foránea referenciando a `users.id` |
| `date` | TEXT | Fecha del registro (`YYYY-MM-DD`) |
| `completed` | BOOLEAN | Estado de cumplimiento (`0` o `1`) |
| `checked_at` | TIMESTAMP | Marca temporal de la confirmación |

### 4. `notification_logs`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | ID de la notificación |
| `user_id` | INTEGER | ID del usuario |
| `date` | TEXT | Fecha de emisión (`YYYY-MM-DD`) |
| `notif_type` | TEXT | Tipo de notificación (`'morning'`, `'rescue'`, `'weekly_report'`, `'habit_<id>'`) |
| `sent_at` | TIMESTAMP | Marca temporal de despacho para evitar duplicados |

---

## 🤖 Enrutador de Intenciones con Gemini NLP

HabitBot analiza cada mensaje de texto libre mediante la API de Google Gemini (modelos `gemini-flash-lite-latest` y `gemini-flash-latest`) solicitando una respuesta estructurada en formato JSON estricto:

```json
{
  "intencion": "CREAR_HABITO" | "VER_REPORTE" | "VER_ESTADO" | "PROBAR_ALERTA" | "CONVERSACION_GENERAL",
  "datos_habito": {
    "titulo": "Leer 20 min",
    "frecuencia": "diario",
    "hora": "22:00"
  }
}
```

### Rutas de Procesamiento:
1. **`CREAR_HABITO`:** Extrae automáticamente el título limpio (en infinitivo, sin la hora), la frecuencia y la hora (en formato 24h `HH:MM`). Registra el hábito en SQLite y responde con un mensaje interactivo con botón `[✏️ Cambiar hora]` para ajustes inmediatos.
2. **`VER_REPORTE`:** Si el usuario pregunta cosas como *"¿cómo me fue esta semana?"* o presiona *"📊 Mi Semana"*, el bot calcula el rendimiento de los últimos 7 días y solicita a Gemini una retroalimentación personalizada.
3. **`VER_ESTADO`:** Si el usuario pide ver sus hábitos o presiona *"📋 Mis Hábitos"*, muestra el tablero del día con casillas interactivas `[⬜]` / `[✅]`.
4. **`PROBAR_ALERTA`:** Si el usuario escribe *"probar alerta"* o pulsa *"⚡ Probar Alerta"*, fuerza la alerta de rescate de racha de inmediato.
5. **`CONVERSACION_GENERAL`:** Si el usuario saluda, agradece o conversa, el bot responde con la personalidad divertida, motivadora y ligeramente sarcástica del búho coach.

> **Resiliencia:** Si la API de Gemini experimenta problemas de red o cuota, el bot activa un clasificador heurístico por expresiones regulares y plantillas de respaldo, garantizando que el servicio nunca se interrumpa.

---

## 🛠️ Instalación y Configuración

### 1. Prerrequisitos
- **Python 3.10** o superior (probado en Python 3.13).
- Token de Telegram Bot de [@BotFather](https://t.me/BotFather).
- API Key de Google Gemini de [Google AI Studio](https://aistudio.google.com/).

### 2. Clonar el Repositorio
```bash
git clone https://github.com/leonardobaca7/habit_Bot.git
cd habit_Bot
```

### 3. Crear y Activar el Entorno Virtual
En Windows (PowerShell):
```powershell
python -m venv .venv
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
Copia el archivo de plantilla `.env.example` a `.env`:
```bash
cp .env.example .env
```
Configura tus credenciales en `.env`:
```env
TELEGRAM_BOT_TOKEN="tu_token_de_telegram"
GEMINI_API_KEY="tu_api_key_de_gemini"
DATABASE_PATH="habitbot.db"
```

---

## ▶️ Ejecución de HabitBot

Inicia el bot y el programador de tareas en segundo plano:
```powershell
.\.venv\Scripts\python.exe main.py
```

Al iniciar, verás en la consola:
```text
INFO - Initializing SQLite database...
INFO - Database initialized successfully.
INFO - APScheduler repeating notification dispatcher configured (every 60s).
INFO - HabitBot handlers and scheduler registered. Starting polling...
```

---

## 🎮 Comandos y Atajos

| Comando / Botón | Descripción |
|---|---|
| `/start` | Registra al usuario y despliega el teclado persistente con 4 accesos rápidos. |
| `📋 Mis Hábitos` | Abre el tablero del día con casillas para marcar/desmarcar hábitos. |
| `📊 Mi Semana` | Muestra el reporte estadístico de cumplimiento semanal con feedback del coach. |
| `➕ Agregar Hábito` | Despliega una guía con ejemplos para registrar hábitos conversacionalmente. |
| `⚡ Probar Alerta` | Genera y envía inmediatamente la alerta de rescate estilo Duolingo con Gemini. |
| `/test_duolingo` | Fuerza la alerta de rescate de racha con botones interactivos. |
| `/test_weekly` | Fuerza la generación del reporte semanal de los últimos 7 días. |
| `/test_morning` | Fuerza el resumen matutino diario. |
| `/status` | Muestra el tablero de progreso del día actual. |
| `/list` | Lista todos los hábitos registrados con opción de eliminación. |
| `/help` | Guía de uso y reglas para mantener viva tu racha. |

---

## 📊 Reporte Semanal Automático de los Domingos

El scheduler inspecciona cada 60 segundos la hora local del usuario. Cada domingo a las **20:00 (8:00 PM)**:
1. Consulta los registros en `daily_logs` de los últimos 7 días.
2. Calcula:
   - Días completados por cada hábito con barra visual `[🟩🟩🟩⬜⬜⬜⬜]`.
   - Porcentaje general de efectividad semanal.
   - Estado de la racha activa.
3. Envía los datos a Gemini API para redactar un mensaje según el desempeño:
   - **>= 80%:** Elogios enérgicos y celebración de la disciplina.
   - **50% - 79%:** Ánimo para no aflojar y buscar el 100%.
   - **< 50%:** Humor dramático de Duolingo para despertar al usuario la próxima semana.
