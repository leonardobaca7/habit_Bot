# HabitBot

Sistema de asistencia conversacional y seguimiento de hábitos para Telegram, desarrollado con arquitectura asíncrona en Python, persistencia relacional con SQLite y procesamiento de lenguaje natural (NLP) mediante la API de Google Gemini.

---

## 1. Descripción General del Proyecto

HabitBot es un asistente automatizado para la creación, seguimiento y consolidación de hábitos diarios. A diferencia de las herramientas tradicionales basadas exclusivamente en comandos estáticos, HabitBot incorpora un enrutador de intenciones por lenguaje natural que permite interactuar de forma conversacional, procesando mensajes libres para registrar hábitos, consultar métricas y recibir recordatorios inteligentes.

### Principios de Diseño
- **Enfoque Amigable y Motivador:** Diseñado bajo una personalidad de compañero cercano y comprensivo que acompaña al usuario de manera auténtica, celebrando el progreso y proporcionando recordatorios positivos sin dramatismo artificial.
- **Tolerancia a Fallos:** Arquitectura con capas de contingencia (fallbacks heurísticos) para asegurar la continuidad operativa del servicio incluso ante indisponibilidad temporal de APIs externas.
- **Rendimiento Asíncrono:** Ejecución no bloqueante basada en `asyncio` tanto para la interfaz de Telegram (`python-telegram-bot`) como para el acceso a datos (`aiosqlite`) y la programación de tareas (`APScheduler`).

---

## 2. Arquitectura de Software y Módulos Principales

El proyecto sigue una estructura modular orientada a la separación de responsabilidades:

```text
habit_Bot/
├── src/
│   ├── bot/                 # Interfaz de Telegram y controladores de eventos
│   │   ├── handlers.py      # Enrutador central de intenciones, comandos y callbacks
│   │   └── __init__.py
│   ├── core/                # Lógica de dominio y reglas de negocio
│   │   ├── habits.py        # Modelado de tableros, listas y teclados interactivos
│   │   ├── streaks.py       # Cálculo de rachas continuas y validaciones temporales
│   │   └── __init__.py
│   ├── database/            # Capa de persistencia asíncrona
│   │   ├── db.py            # Esquema relacional, índices y migraciones automáticas
│   │   ├── queries.py       # Consultas SQL optimizadas y transacciones
│   │   └── __init__.py
│   ├── scheduler/           # Motor de tareas programadas en segundo plano
│   │   ├── jobs.py          # Planificador de resúmenes, recordatorios y reporte semanal
│   │   └── __init__.py
│   └── services/            # Integración con servicios cognitivos
│       ├── ai_service.py    # Enrutador NLP, extracción estructurada JSON y feedback
│       └── __init__.py
├── Procfile                 # Declaración del proceso para plataformas PaaS
├── runtime.txt              # Declaración de la versión de runtime de Python
├── main.py                  # Punto de entrada de la aplicación y ciclo de polling
├── requirements.txt         # Dependencias de producción
├── .env.example             # Plantilla de configuración de variables de entorno
├── .gitignore               # Exclusión de credenciales, binarios y base de datos
└── README.md                # Documentación técnica del sistema
```

### Componentes del Sistema

1. **Telegram Bot Layer (`src/bot`):**
   Manejo de actualizaciones asíncronas con `python-telegram-bot` v21. Incluye teclado persistente (`ReplyKeyboardMarkup`) para acceso rápido y teclados en línea (`InlineKeyboardMarkup`) para confirmaciones interactivas de hábitos.

2. **Capa de Persistencia Relacional (`src/database`):**
   Implementada sobre SQLite 3 mediante `aiosqlite`. Cuenta con transacciones atómicas, índices por fecha y clave foránea, y un modelo de datos normalizado:
   - `users`: Identificador de Telegram, nombre, zona horaria, hora matutina y contador de racha activa.
   - `habits`: Título del hábito, frecuencia y hora programada de ejecución.
   - `daily_logs`: Registros de cumplimiento diario por hábito y usuario.
   - `notification_logs`: Control de emisión de recordatorios para evitar notificaciones duplicadas.

3. **Motor de Tareas Programadas (`src/scheduler`):**
   Operado mediante `APScheduler` integrado al `JobQueue` de Telegram. Evalúa cada 60 segundos las condiciones de despacho de acuerdo a la zona horaria del usuario:
   - Resumen matutino diario a la hora configurada (por defecto `08:00`).
   - Notificación de recordatorio amigable si existen hábitos pendientes transcurridas 6.5 horas desde la hora matutina.
   - Notificaciones individuales en el horario programado para cada hábito específico.
   - Reporte semanal de rendimiento todos los domingos a las `20:00`.

4. **Procesamiento de Lenguaje Natural (`src/services`):**
   Conexión con la API de Google Gemini (`gemini-flash-lite-latest` y `gemini-flash-latest`). Emplea respuestas estructuradas (`response_mime_type: application/json`) para clasificar intenciones y extraer parámetros clave (título normalizado en infinitivo, frecuencia y hora en formato 24h).

---

## 3. Requisitos y Configuración del Entorno

### Requisitos Previos
- Python 3.10 o superior (recomendado: Python 3.11 / 3.12 / 3.13).
- Token de bot obtenido a través de [@BotFather](https://t.me/BotFather).
- Clave de API de Google Gemini obtenida desde [Google AI Studio](https://aistudio.google.com/).

### Instalación Local

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/leonardobaca7/habit_Bot.git
   cd habit_Bot
   ```

2. **Crear y activar el entorno virtual:**
   - En Linux / macOS:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - En Windows (PowerShell):
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   Cree un archivo `.env` a partir de la plantilla proporcionada:
   ```bash
   cp .env.example .env
   ```
   Defina las siguientes variables en `.env`:
   ```ini
   TELEGRAM_BOT_TOKEN="tu_token_de_telegram"
   GEMINI_API_KEY="tu_api_key_de_gemini"
   DATABASE_PATH="habitbot.db"
   ```

5. **Ejecutar la aplicación:**
   ```bash
   python main.py
   ```

---

## 4. Guía de Uso Conversacional e Interfaz

### Enrutador de Intenciones por Lenguaje Natural

El usuario puede interactuar con lenguaje libre sin necesidad de recordar comandos sintácticos. El enrutador clasifica el mensaje en una de cinco intenciones principales:

| Intención | Ejemplos de Entrada | Comportamiento del Sistema |
|---|---|---|
| `CREAR_HABITO` | "Quiero leer 20 min a las 22:00", "Tomar 2L de agua" | Extrae título, frecuencia y hora; guarda en SQLite y ofrece botón de ajuste. |
| `VER_REPORTE` | "¿Cómo me fue esta semana?", "Dame mi resumen semanal" | Calcula estadísticas de los últimos 7 días y genera feedback reflexivo. |
| `VER_ESTADO` | "Mis hábitos", "¿Qué tengo pendiente hoy?", "Ver racha" | Despliega el tablero con casillas interactivas `[⬜]` / `[✅]`. |
| `PROBAR_ALERTA` | "Probar alerta", "Haz un recordatorio de prueba" | Envía inmediatamente la notificación de recordatorio con botones interactivos. |
| `CONVERSACION_GENERAL` | "Hola", "Gracias", "¿Cómo estás?" | Responde con tono amigable y cercano como compañero de hábitos. |

### Interfaz de Botones Rápidos (ReplyKeyboard)

Para agilizar la navegación en dispositivos móviles, se incluye un menú permanente con cuatro opciones:
- **`📋 Mis Hábitos`:** Abre el tablero interactivo para marcar o desmarcar actividades.
- **`📊 Mi Semana`:** Consulta el porcentaje de cumplimiento y métricas semanales.
- **`➕ Agregar Hábito`:** Muestra instrucciones y ejemplos para registrar nuevas metas.
- **`⚡ Probar Alerta`:** Simula el envío de una notificación push de recordatorio.

### Comandos de Control y Depuración

- `/start`: Inicializa el registro del usuario y despliega la bienvenida y el menú principal.
- `/status`: Muestra el estado del día actual con botones de acción.
- `/list`: Lista todos los hábitos registrados con opción de eliminación.
- `/help`: Despliega la guía de uso y reglas de racha.
- `/test_duolingo`: Disparador manual para verificar el recordatorio push de racha.
- `/test_weekly`: Disparador manual para generar el reporte semanal de los últimos 7 días.
- `/test_morning`: Disparador manual para evaluar la notificación matutina.

---

## 5. Instrucciones de Despliegue en Servidores Nube

HabitBot está preparado para ejecutarse de forma continua como un servicio de tipo **Background Worker** en plataformas PaaS como Render o Railway.

### Despliegue en Railway

1. Cree un proyecto nuevo en [Railway](https://railway.app/) y seleccione **Deploy from GitHub repo**.
2. Vincule el repositorio `habit_Bot`.
3. En la pestaña **Variables**, configure las siguientes variables de entorno:
   - `TELEGRAM_BOT_TOKEN`: Token proporcionado por BotFather.
   - `GEMINI_API_KEY`: Clave de API de Google AI Studio.
   - `DATABASE_PATH`: `/app/data/habitbot.db` (o `habitbot.db`).
4. *(Opcional pero recomendado para producción)* Añada un volumen persistente montado en `/app/data` para que el archivo SQLite persista tras los despliegues.
5. Railway detectará automáticamente el archivo `Procfile` ejecutando el comando de arranque:
   ```bash
   worker: python main.py
   ```

### Despliegue en Render

1. En el panel de [Render](https://render.com/), seleccione **New +** > **Background Worker**.
2. Conecte el repositorio del proyecto.
3. Configure los parámetros de compilación y ejecución:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
4. En la sección **Advanced** > **Environment Variables**, ingrese:
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `DATABASE_PATH`
5. *(Opcional)* Si utiliza un disco persistente en Render, configure el punto de montaje y apunte `DATABASE_PATH` hacia esa ruta.
6. Guarde y despliegue el servicio. El bot iniciará el ciclo de polling y el programador de tareas automáticamente.
