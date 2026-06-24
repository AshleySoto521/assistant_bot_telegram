# 🤖 Bot Paisa — Buzón Unificado de Leads (v4.0 · Modo Privado Directo)

Bot de Telegram para creadores de contenido / marcas personales que funciona como un **buzón unificado anónimo**: capta gente desde tu grupo con publicaciones automáticas, redirige todas las conversaciones privadas hacia tu chat personal organizadas por hilos, y te deja responder a cada persona sin que sepan que hay un bot de por medio.

> **Sin IA.** Esta versión **no** usa modelos de lenguaje. Cada mensaje del usuario llega directo a ti (el admin) y tú respondes manualmente. Es simple, predecible y de **costo 0** (Telegram + SQLite local + hosting en tu PC).

---

## 🧭 ¿Cómo funciona? (arquitectura)

```
Usuario (privado)  ──►  BOT  ──►  Tu chat de Admin (hilos por persona)
        ▲                                   │
        └───────────  BOT  ◄────────────────┘   (tú respondes; el bot reenvía)
```

1. Un usuario le escribe al bot por privado (texto, foto, video, voz o audio).
2. El bot **guarda** el mensaje en SQLite y crea (o reutiliza) un **hilo** en tu chat: un mensaje "ancla" con `👤 Nombre (ID)`.
3. Reenvía el contenido a tu chat como **respuesta** a ese hilo, para que todo quede ordenado por persona.
4. Tú **respondes** haciendo *Reply* a cualquier mensaje que tenga el `(ID)` entre paréntesis; el bot extrae ese ID y le hace llegar tu respuesta al usuario.
5. El usuario nunca sabe que hubo un intermediario: ve un chat normal contigo.

### Estados de un lead (`modo`)
- **`nuevo`** — aún no registrado / sin hilo.
- **`humano`** — conversación activa, hilo abierto en tu chat.
- **`cerrado`** — ticket cerrado (sigue en la base para promos y reapertura).

---

## ✨ Funcionalidades

### Para el usuario
- **`/start`** — saludo de bienvenida.
- Puede enviar **texto y multimedia** (foto, video, nota de voz, audio); todo se reenvía a tu hilo.
- Al escribir por primera vez recibe una respuesta automática ("ya te leo, te respondo en un momentico").

### Para ti (admin)
- **Responder por *Reply*** — respondes a un mensaje con `(ID)` y el bot reenvía tu texto o multimedia **solo a ese usuario**.
- **Publicar multimedia al grupo** — si envías una foto/video al bot **sin** responder a nadie, lo publica en el grupo con un botón de *Call To Action*.
- **Hilos ordenados** — cada persona tiene su propio hilo; al abrir un lead nuevo recibes su historial automáticamente.

### Automatizaciones
- **📢 Publicaciones automáticas** — cada **6 horas**, dentro del horario permitido, el bot publica en el grupo un mensaje "gancho" aleatorio con un botón **"Escríbeme por privado"**.
- **🔁 Seguimiento de leads fríos** — cada hora revisa los leads activos: si tú respondiste y el usuario lleva **6 horas en silencio**, le envía **un** mensaje de reenganche (una sola vez, hasta que vuelva a escribir). Solo dentro del horario permitido, y te avisa en el hilo cuando lo hace.
- **⏰ Control de horario** — todas las publicaciones y seguimientos respetan la franja `HORA_INICIO_POST`–`HORA_FIN_POST` para no escribir de madrugada.

---

## 🎮 Comandos

### Usuario
| Comando | Descripción |
|---|---|
| `/start` | Inicia la conversación con el bot |

### Administrador (solo tu `ID_ADMIN`)
| Comando | Descripción |
|---|---|
| `/post <texto>` | Publica un mensaje al grupo con botón de contacto |
| `/promo <texto>` | Envía una promo a **todos** los leads (activos + cerrados) |
| `/leads` | Lista los leads activos |
| `/stats` | Estadísticas: usuarios, leads, mensajes y últimos activos |
| `/historial <id>` | Muestra el historial de conversación de un usuario |
| `/abrir <id>` | Reabre y trae arriba el hilo de un lead |
| `/cerrar` | Cierra el ticket del lead (respondiendo a su mensaje) |
| `/cerrarid <id>` | Cierra un ticket por ID, sin necesidad de *Reply* |
| `/cerrartodos` | Cierra todos los leads activos de golpe |

> El **menú `/`** de Telegram se configura solo al arrancar: tú ves todos los comandos de admin; los usuarios normales solo ven `/start`.

---

## 🗄️ Base de datos (SQLite local — `historial_chat.db`)

**Tabla `usuarios`**
| Columna | Descripción |
|---|---|
| `user_id` | ID de Telegram del usuario (clave primaria) |
| `modo` | Estado: `nuevo` / `humano` / `cerrado` |
| `nombre` | Nombre del usuario |
| `thread_msg_id` | ID del mensaje "ancla" del hilo en tu chat |
| `seguimiento_enviado` | 1 si ya se le envió el reenganche por silencio (evita repetir) |

**Tabla `mensajes`**
| Columna | Descripción |
|---|---|
| `id` | Autoincremental |
| `user_id` | A qué usuario pertenece |
| `texto` | Contenido (o `[MEDIA]` / `[PROMO] ...`) |
| `fecha` | Marca de tiempo |
| `tipo` | `entrada_usuario` (lo que escribe él/ella) o `salida_humano` (lo que envías tú) |

La estructura se crea/migra sola al iniciar (`iniciar_db()`), así que no hay que hacer nada manual.

---

## 🛠️ Requisitos

- **Python 3.10+**
- Un **bot de Telegram** creado con [@BotFather](https://t.me/BotFather)
- Tu **ID de Telegram** y el **ID del grupo** (puedes obtenerlos con `detector_ids.py` o [@userinfobot](https://t.me/userinfobot))

## 📦 Instalación

```bash
pip install -r requirements.txt
```

Dependencias realmente usadas por esta versión:

```text
python-telegram-bot[job-queue]
python-dotenv
pytz
```

> `google-generativeai` aparece en `requirements.txt` por la versión anterior con IA, pero **esta versión no lo usa**.

## ⚙️ Configuración (`.env`)

Crea un archivo `.env` en la raíz con estas variables (las únicas que usa el bot actual):

```env
TOKEN_TELEGRAM=tu_token_aqui
ID_TU_GRUPO=-1001234567890   # ID del grupo (con el signo menos)
ID_ADMIN=123456789           # Tu ID personal (permisos de admin)

# Horario de publicaciones y seguimientos (formato 24h)
HORA_INICIO_POST=09:00
HORA_FIN_POST=22:00
TIMEZONE=America/Mexico_City  # Ej: America/Bogota, America/New_York
```

> Las variables `GOOGLE_API_KEY` y `VERSION_PRO` de versiones anteriores **ya no se usan** y pueden eliminarse.

---

## ▶️ Ejecución

### Manual
```bash
python main.py
```

### Con PM2 (recomendado, para que corra en segundo plano)
```bash
pm2 start ecosystem.config.js
pm2 restart bot-telegram   # tras cada cambio en el código
pm2 logs bot-telegram      # ver registros
pm2 list                   # estado de los procesos
```

> El bot corre en tu PC: **debe estar encendida y con PM2 activo** para responder y publicar.

### Posteo sin el celular
No necesitas el teléfono: instala **Telegram Desktop** (o usa [web.telegram.org](https://web.telegram.org)) en la misma computadora, abre el chat del bot y usa los mismos comandos con el teclado.

---

## ⚙️ Parámetros ajustables (en `main.py`)

| Qué | Dónde | Valor actual |
|---|---|---|
| Frecuencia de posts automáticos | `run_repeating(generar_post_automatico, interval=...)` | `21600` s (6 h) |
| Frecuencia del chequeo de leads fríos | `run_repeating(seguimiento_leads_frios, interval=...)` | `3600` s (1 h) |
| Horas de silencio para reenganchar | `HORAS_LEAD_FRIO` | `6` |
| Frases de posts automáticos | `MENSAJES_AUTO_POST` | lista editable |
| Frases de reenganche | `MENSAJES_SEGUIMIENTO` | lista editable |

---

## 💰 Costo de operación

**0 €/0 $** — Telegram Bot API, SQLite local y hosting en tu propia PC. Sin servicios de pago.
