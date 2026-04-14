import logging
import sqlite3
import os
import asyncio
import re
import json
from dotenv import load_dotenv
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types
import pytz
import sys

# ================= FIX UTF-8 PARA WINDOWS + PM2 =================
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
# ================================================================

# ================= CONFIGURACIÓN SEGURA =================
load_dotenv() # Carga las claves del archivo .env

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Configuración de horarios para publicaciones automáticas
HORA_INICIO_POST = os.getenv("HORA_INICIO_POST", "09:00")  # Default 9 AM
HORA_FIN_POST = os.getenv("HORA_FIN_POST", "22:00")        # Default 10 PM
TIMEZONE = os.getenv("TIMEZONE", "America/Mexico_City")     # Default CDMX

# Configuración PRO (activación de features adicionales)
VERSION_PRO = os.getenv("VERSION_PRO", "false").lower() == "true"

try:
    ID_TU_GRUPO = int(os.getenv("ID_TU_GRUPO"))
    ID_ADMIN = int(os.getenv("ID_ADMIN"))
except TypeError:
    print("❌ ERROR: Revisa tu archivo .env. Los IDs deben ser números.")
    exit()

if not TOKEN_TELEGRAM or not GOOGLE_API_KEY:
    print("❌ ERROR: Faltan tokens en el archivo .env")
    exit()
# ========================================================

client = genai.Client(api_key=GOOGLE_API_KEY)
MODELO_IA = 'gemini-2.0-flash'
SAFETY_SETTINGS = [
    types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
    types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
    types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
    types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
]

def generar_contenido(prompt):
    """Wrapper para llamar a la IA con configuración de seguridad"""
    response = client.models.generate_content(
        model=MODELO_IA,
        contents=prompt,
        config=types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS)
    )
    return response.text

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- BASE DE DATOS LOCAL ---
def iniciar_db():
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (user_id INTEGER PRIMARY KEY, modo TEXT, nombre TEXT, thread_msg_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mensajes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, texto TEXT, fecha TEXT, tipo TEXT)''')
    # Migración: agregar thread_msg_id si no existe (para DBs existentes)
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN thread_msg_id INTEGER")
    except sqlite3.OperationalError:
        pass  # La columna ya existe
    conn.commit()
    conn.close()

def guardar_mensaje(user_id, texto, tipo):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    texto_guardar = texto if texto else "[FOTO/MEDIA]"
    c.execute("INSERT INTO mensajes (user_id, texto, fecha, tipo) VALUES (?, ?, ?, ?)", (user_id, texto_guardar, fecha, tipo))
    conn.commit()
    conn.close()

def set_modo_usuario(user_id, modo, nombre="Usuario", thread_msg_id=None):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO usuarios (user_id, modo, nombre, thread_msg_id) VALUES (?, ?, ?, ?)", (user_id, modo, nombre, thread_msg_id))
    conn.commit()
    conn.close()

def get_thread_msg_id(user_id):
    """Obtiene el message_id del hilo de conversación del lead"""
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("SELECT thread_msg_id FROM usuarios WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res and res[0] else None

def get_modo_usuario(user_id):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("SELECT modo FROM usuarios WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "ia"

def obtener_historial_usuario(user_id, limite=20):
    """Obtiene el historial de conversación de un usuario para contexto"""
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("""
        SELECT texto, fecha, tipo
        FROM mensajes
        WHERE user_id=?
        ORDER BY fecha DESC
        LIMIT ?
    """, (user_id, limite))
    mensajes = c.fetchall()
    conn.close()

    # Formatear el historial de forma legible
    historial_formateado = "📜 HISTORIAL DE CONVERSACIÓN:\n" + "="*50 + "\n\n"

    for texto, fecha, tipo in reversed(mensajes):  # Mostrar en orden cronológico
        emoji = "👤" if tipo == "entrada_usuario" else "🤖"
        rol = "Usuario" if tipo == "entrada_usuario" else "IA"
        historial_formateado += f"{emoji} [{fecha}] {rol}:\n{texto}\n\n"

    historial_formateado += "="*50
    return historial_formateado

def limpiar_respuesta_ia(texto):
    """Elimina texto meta de la IA y deja solo el contenido real del mensaje"""
    # Patrones comunes de texto meta que la IA puede incluir
    patrones_a_eliminar = [
        r'^.*?aquí\s+(tienes|está|va)\s+(el\s+)?mensaje.*?:\s*',
        r'^.*?perfecto[,.]?\s+',
        r'^claro[,.]?\s+',
        r'^.*?voy\s+a\s+(escribir|generar|crear).*?:\s*',
        r'^.*?mensaje\s+para\s+(tu\s+)?grupo.*?:\s*',
        r'^.*?para\s+(el\s+)?telegram.*?:\s*',
    ]

    texto_limpio = texto.strip()

    # Aplicar cada patrón de forma case-insensitive
    for patron in patrones_a_eliminar:
        texto_limpio = re.sub(patron, '', texto_limpio, flags=re.IGNORECASE | re.MULTILINE)

    return texto_limpio.strip()

def esta_en_horario_permitido():
    """Verifica si la hora actual está dentro del horario configurado para publicaciones"""
    try:
        tz = pytz.timezone(TIMEZONE)
        ahora = datetime.now(tz)
        hora_actual = ahora.time()

        # Parsear horarios del .env
        hora_inicio = datetime.strptime(HORA_INICIO_POST, "%H:%M").time()
        hora_fin = datetime.strptime(HORA_FIN_POST, "%H:%M").time()

        # Verificar si está en el rango
        if hora_inicio <= hora_fin:
            # Caso normal: 09:00 - 21:00
            return hora_inicio <= hora_actual <= hora_fin
        else:
            # Caso que cruza medianoche: 22:00 - 02:00
            return hora_actual >= hora_inicio or hora_actual <= hora_fin
    except Exception as e:
        print(f"⚠️ Error verificando horario: {e}")
        return True  # Si hay error, permitir publicación por defecto

# ==============================================================================
#  LOGICA DE PUBLICACIÓN AUTOMÁTICA
# ==============================================================================

async def generar_post_automatico(context: ContextTypes.DEFAULT_TYPE):
    """Se ejecuta automáticamente según el tiempo programado"""
    print("⏰ Ejecutando tarea automática: Generando post...")

    # Verificar si estamos en horario permitido
    if not esta_en_horario_permitido():
        tz = pytz.timezone(TIMEZONE)
        hora_actual = datetime.now(tz).strftime("%H:%M")
        print(f"⏸️ Post automático omitido. Hora actual: {hora_actual} (Horario: {HORA_INICIO_POST}-{HORA_FIN_POST})")
        return

    # Crear solicitud en formato JSON para que la IA la entienda mejor
    solicitud_base = {
        "tarea": "generar_post_telegram",
        "personaje": {
            "nombre": "Fer Ruiz",
            "edad": 27,
            "origen": "Medellín, Colombia",
            "ubicacion_actual": "CDMX, México",
            "profesion": "influencer, Modelo de contenido para adutos"
        },
        "caracteristicas_mensaje": {
            "longitud": "corto (máximo 2-3 líneas)",
            "tono": ["coqueto", "picarón", "directo", "paisa"],
            "objetivo": "generar interacción y mensajes privados",
            "palabras_clave": ["mor", "bebé", "parce", "obvio"],
            "emojis_sugeridos": ["🔥", "👀", "😈", "💅", "💋"],
            "evitar": ["saludos genéricos como 'hola chicos'", "introduciones", "explicaciones meta"]
        },
        "instruccion": "Genera SOLO el texto del mensaje que se publicará, sin introducciones ni explicaciones adicionales."
    }

    # Feature PRO: Posts más personalizados y variados
    if VERSION_PRO:
        solicitud_base["variantes_pro"] = {
            "estilos_disponibles": [
                "pregunta_provocativa",
                "historia_corta_intrigante",
                "consejo_atrevido",
                "confesion_picante"
            ],
            "instruccion": "Alterna entre los estilos disponibles y hazlo único cada vez"
        }

    # Convertir la solicitud a JSON y crear el prompt
    solicitud_json = json.dumps(solicitud_base, ensure_ascii=False, indent=2)
    prompt = f"""Recibiste la siguiente solicitud en formato JSON para mejor comprensión:

{solicitud_json}

Basándote en esta solicitud estructurada, genera el mensaje solicitado. Responde ÚNICAMENTE con el texto del mensaje, nada más."""

    try:
        mensaje_ia = generar_contenido(prompt)

        # Limpiar respuesta de la IA para eliminar texto meta
        mensaje_limpio = limpiar_respuesta_ia(mensaje_ia)
        mensaje_final = f"\n\n{mensaje_limpio}"

        keyboard = [[InlineKeyboardButton("🔥 Escríbeme por privado", url=f"https://t.me/{context.bot.username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(chat_id=ID_TU_GRUPO, text=mensaje_final, reply_markup=reply_markup)
        print(f"✅ Post publicado exitosamente (PRO: {VERSION_PRO})")

    except Exception as e:
        print(f"❌ Error en el post automático: {e}")

# ==============================================================================
#  EL CEREBRO INTELIGENTE (IA CLASIFICADORA Y PERSONALIDAD)
# ==============================================================================

async def manejar_mensaje_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private": return
    user_id = update.effective_user.id
    texto = update.message.text
    nombre = update.effective_user.first_name
    
    guardar_mensaje(user_id, texto, "entrada_usuario")
    
    # Si ya está en modo humano, reenvía al hilo del lead
    modo = get_modo_usuario(user_id)
    if modo == "humano":
        thread_id = get_thread_msg_id(user_id)
        await context.bot.send_message(
            chat_id=ID_ADMIN,
            text=f"💬 {nombre} ({user_id}):\n{texto}",
            reply_to_message_id=thread_id
        )
        return

    # --- CLASIFICACIÓN + RESPUESTA EN UNA SOLA LLAMADA ---
    try:
        prompt_base = f"""Eres "Fer Ruiz", una influencer colombiana (paisa) de 27 años viviendo en CDMX.
Tu tono es: Coqueta, picaróna, relajada y muy "de barrio" pero fresa.
Palabras obligatorias: Mor, bebé, parce, nea, qué más pues, obvio bobis.
NUNCA respondas como robot ("Soy una IA", "En qué puedo ayudarte").
Si te saludan, no digas "Hola". Di algo como: "Quiubo mor", "Hola bebé".
Usa emojis en cada mensaje: 🔥, 😈, 👀, 💅.
Tus respuestas deben ser CORTAS (máximo 2 líneas).

Ejemplos de cómo respondes:
User: ¿Qué haces?
Tú: Aquí pensando en cuándo me vas a invitar a salir mor 💅

User: Eres un robot?
Tú: Obvio no bobis, soy tu tormento 😈

User: Te ves bien
Tú: Yo sé que te encanto parce, no lo niegues 💅🔥

REGLA IMPORTANTE DE CLASIFICACIÓN:
Analiza el mensaje del usuario. Si detectas intención de COMPRA, PRECIOS, CONTRATAR o COLABORAR, tu respuesta DEBE empezar EXACTAMENTE con "[VENTA]" seguido de un mensaje coqueto relacionado.
Si es charla casual, saludo o broma, responde normal SIN ninguna etiqueta.

Ejemplos de clasificación:
User: "Cuánto cobras?"
Tú: [VENTA] Uff mi amor, te paso toda la info para tratarte como mereces 👀🔥

User: "Quiero comprar contenido"
Tú: [VENTA] Ay bebé, obvio que sí, déjame te cuento todo mor 💅

User: "Hola bb"
Tú: Quiubo mor, qué más pues 😈🔥"""

        # Feature PRO: Memoria conversacional
        if VERSION_PRO:
            conn = sqlite3.connect('historial_chat.db')
            c = conn.cursor()
            c.execute("""
                SELECT texto, tipo FROM mensajes
                WHERE user_id=?
                ORDER BY fecha DESC
                LIMIT 5
            """, (user_id,))
            mensajes_recientes = c.fetchall()
            conn.close()

            contexto_previo = "\n\nCONTEXTO DE LA CONVERSACIÓN RECIENTE:\n"
            for msg, tipo in reversed(mensajes_recientes):
                rol = "Usuario" if tipo == "entrada_usuario" else "Tú"
                contexto_previo += f"{rol}: {msg}\n"

            prompt_final = prompt_base + contexto_previo + f"\n\nAHORA RESPONDE (considera el contexto):\nUser: \"{texto}\"\nTú:"
        else:
            prompt_final = prompt_base + f"\n\nAHORA RESPONDE:\nUser: \"{texto}\"\nTú:"

        respuesta_ia = generar_contenido(prompt_final).strip()
        print(f"🧠 IA Responde a '{texto}' -> {respuesta_ia[:80]}...")

        # Detectar si la IA clasificó como VENTA
        if respuesta_ia.startswith("[VENTA]"):
            mensaje_usuario = respuesta_ia.replace("[VENTA]", "").strip()
            await update.message.reply_text(mensaje_usuario)
            guardar_mensaje(user_id, mensaje_usuario, "salida_ia")

            # ACTIVAR MODO HUMANO
            notificacion = f"🚨 LEAD CALIENTE (IA) 🚨\nUsuario: {nombre} ({user_id})\nIntención Detectada: Negocios\nMensaje que activó lead: {texto}"
            msg_notificacion = await context.bot.send_message(chat_id=ID_ADMIN, text=notificacion)
            set_modo_usuario(user_id, "humano", nombre, thread_msg_id=msg_notificacion.message_id)

            # Enviar historial como respuesta al hilo del lead
            historial = obtener_historial_usuario(user_id, limite=20)
            if historial and len(historial) > 100:
                max_length = 4000
                if len(historial) > max_length:
                    chunks = [historial[i:i+max_length] for i in range(0, len(historial), max_length)]
                    for i, chunk in enumerate(chunks):
                        await context.bot.send_message(chat_id=ID_ADMIN, text=f"📋 Contexto (parte {i+1}/{len(chunks)}):\n{chunk}", reply_to_message_id=msg_notificacion.message_id)
                else:
                    await context.bot.send_message(chat_id=ID_ADMIN, text=historial, reply_to_message_id=msg_notificacion.message_id)
        else:
            # MODO CHAT normal
            await update.message.reply_text(respuesta_ia)
            guardar_mensaje(user_id, respuesta_ia, "salida_ia")

    except Exception as e:
        print(f"Error IA: {e}")
        await update.message.reply_text("Dame un segundo mor, estoy revisando algo...")

# ==============================================================================
#  FUNCIONES DE ADMINISTRADOR (TÚ)
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    set_modo_usuario(user.id, "ia", user.first_name)

    mensaje_bienvenida = f"¡Hola {user.first_name}! ¿Qué se te antoja hacer hoy mor?"

    # Feature PRO: Mensaje de bienvenida personalizado
    if VERSION_PRO:
        mensaje_bienvenida += " ✨\n\n💎 Que pues mor, estoy con unas ganas de que nos veamos... 🔥"

    await update.message.reply_text(mensaje_bienvenida)

async def admin_responde_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message: return

    # Buscar el ID del usuario en toda la cadena de respuestas
    texto_original = update.message.reply_to_message.text or ""
    match = re.search(r'\((\d{5,})\)', texto_original)

    if match:
        try:
            id_usuario_destino = int(match.group(1))
            await context.bot.send_message(chat_id=id_usuario_destino, text=update.message.text)

            # Confirmar y agrupar en el hilo del lead
            thread_id = get_thread_msg_id(id_usuario_destino)
            await context.bot.send_message(
                chat_id=ID_ADMIN,
                text=f"✅ Tú respondiste:\n{update.message.text}",
                reply_to_message_id=thread_id
            )
            guardar_mensaje(id_usuario_destino, update.message.text, "salida_humano")
        except Exception as e:
            await update.message.reply_text(f"❌ Error al enviar: {e}")
    else:
        await update.message.reply_text("⚠️ No encontré el ID. Responde a un mensaje del bot que tenga el ID entre paréntesis.")

async def cerrar_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cerrar para devolver al usuario a la IA"""
    if update.effective_user.id != ID_ADMIN: return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Tienes que responder (Reply) al mensaje del usuario para cerrar su ticket.")
        return

    texto_original = update.message.reply_to_message.text or ""
    match = re.search(r'\((\d{5,})\)', texto_original)

    if match:
        id_usuario = int(match.group(1))
        set_modo_usuario(id_usuario, "ia") # <--- AQUÍ SE RESETEA EL MODO
        
        await update.message.reply_text(f"✅ Ticket cerrado. El usuario {id_usuario} regresa con la IA.")
        await context.bot.send_message(chat_id=id_usuario, text="Cualquier cosa no dudes en avisarme mor. 👋")
    else:
        await update.message.reply_text("❌ No encontré el ID para cerrar el ticket.")

async def publicar_media_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Publica fotos o videos del admin al grupo"""
    texto_caption = update.message.caption if update.message.caption else ""
    keyboard = [[InlineKeyboardButton("🔥 Escribeme al privado mor", url=f"https://t.me/{context.bot.username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    tipo = "Video" if update.message.video else "Foto"

    try:
        await context.bot.copy_message(chat_id=ID_TU_GRUPO, from_chat_id=ID_ADMIN, message_id=update.message.message_id, caption=texto_caption, reply_markup=reply_markup)
        await update.message.reply_text(f"✅ {tipo} publicado/a en el grupo.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def postear_texto_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ID_ADMIN: return

    mensaje = " ".join(context.args)
    if not mensaje:
        await update.message.reply_text("❌ Error. Uso: /post Hola a todos")
        return

    keyboard = [[InlineKeyboardButton("🔥 Escribeme en privado mor!", url=f"https://t.me/{context.bot.username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(chat_id=ID_TU_GRUPO, text=mensaje, reply_markup=reply_markup)
        await update.message.reply_text("✅ Mensaje publicado.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def ver_historial_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historial [user_id] para que el admin vea el historial de un usuario"""
    if update.effective_user.id != ID_ADMIN:
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Uso: /historial [user_id]\nEjemplo: /historial 123456789")
        return

    try:
        user_id = int(context.args[0])
        historial = obtener_historial_usuario(user_id, limite=30)

        if len(historial) > 100:
            # Dividir en chunks si es necesario
            max_length = 4000
            if len(historial) > max_length:
                chunks = [historial[i:i+max_length] for i in range(0, len(historial), max_length)]
                for i, chunk in enumerate(chunks):
                    await update.message.reply_text(f"📋 Parte {i+1}/{len(chunks)}:\n{chunk}")
            else:
                await update.message.reply_text(historial)
        else:
            await update.message.reply_text(f"⚠️ No hay historial suficiente para el usuario {user_id}")

    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número válido")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def ver_leads_activos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /leads para ver todos los leads activos (solo admin)"""
    if update.effective_user.id != ID_ADMIN:
        return

    try:
        conn = sqlite3.connect('historial_chat.db')
        c = conn.cursor()
        c.execute("""
            SELECT u.nombre, u.user_id, MAX(m.fecha) as ultimo_msg
            FROM usuarios u
            LEFT JOIN mensajes m ON u.user_id = m.user_id
            WHERE u.modo='humano'
            GROUP BY u.user_id
            ORDER BY ultimo_msg DESC
        """)
        leads = c.fetchall()
        conn.close()

        if not leads:
            await update.message.reply_text("✅ No hay leads activos en este momento.")
            return

        texto = f"🔥 LEADS ACTIVOS ({len(leads)})\n{'='*40}\n\n"
        for i, (nombre, uid, ultimo_msg) in enumerate(leads, 1):
            fecha = ultimo_msg if ultimo_msg else "Sin mensajes"
            texto += f"{i}. {nombre} ({uid})\n   📅 Último msg: {fecha}\n\n"

        texto += f"{'='*40}\n💡 Usa /cerrar (reply) para cerrar uno\n💡 Usa /cerrartodos para cerrar todos"
        await update.message.reply_text(texto)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cerrar_todos_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cerrartodos para cerrar todos los leads activos de una vez"""
    if update.effective_user.id != ID_ADMIN:
        return

    try:
        conn = sqlite3.connect('historial_chat.db')
        c = conn.cursor()
        c.execute("SELECT user_id, nombre FROM usuarios WHERE modo='humano'")
        leads = c.fetchall()

        if not leads:
            conn.close()
            await update.message.reply_text("✅ No hay leads activos para cerrar.")
            return

        c.execute("UPDATE usuarios SET modo='ia' WHERE modo='humano'")
        conn.commit()
        conn.close()

        # Notificar a cada usuario
        errores = 0
        for user_id, nombre in leads:
            try:
                await context.bot.send_message(chat_id=user_id, text="Cualquier cosa no dudes en avisarme mor. 👋")
            except Exception:
                errores += 1

        resumen = f"✅ {len(leads)} lead(s) cerrado(s):\n\n"
        for user_id, nombre in leads:
            resumen += f"• {nombre} ({user_id})\n"

        if errores:
            resumen += f"\n⚠️ {errores} usuario(s) no pudieron ser notificados."

        await update.message.reply_text(resumen)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def ver_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats para ver estadísticas del bot (solo admin)"""
    if update.effective_user.id != ID_ADMIN:
        return

    try:
        conn = sqlite3.connect('historial_chat.db')
        c = conn.cursor()

        # Total de usuarios
        c.execute("SELECT COUNT(DISTINCT user_id) FROM usuarios")
        total_usuarios = c.fetchone()[0]

        # Usuarios en modo humano (leads activos)
        c.execute("SELECT COUNT(*) FROM usuarios WHERE modo='humano'")
        leads_activos = c.fetchone()[0]

        # Total de mensajes
        c.execute("SELECT COUNT(*) FROM mensajes")
        total_mensajes = c.fetchone()[0]

        # Últimos 5 usuarios activos
        c.execute("""
            SELECT u.nombre, u.user_id, u.modo, COUNT(m.id) as msg_count
            FROM usuarios u
            LEFT JOIN mensajes m ON u.user_id = m.user_id
            GROUP BY u.user_id
            ORDER BY MAX(m.fecha) DESC
            LIMIT 5
        """)
        usuarios_recientes = c.fetchall()
        conn.close()

        # Formatear respuesta
        stats = f"📊 ESTADÍSTICAS DEL BOT\n{'='*40}\n\n"
        stats += f"👥 Total usuarios: {total_usuarios}\n"
        stats += f"🔥 Leads activos: {leads_activos}\n"
        stats += f"💬 Total mensajes: {total_mensajes}\n"
        stats += f"💎 Modo PRO: {'Activado' if VERSION_PRO else 'Desactivado'}\n"
        stats += f"⏰ Horario posts: {HORA_INICIO_POST} - {HORA_FIN_POST}\n\n"
        stats += f"📋 ÚLTIMOS 5 USUARIOS ACTIVOS:\n"

        for nombre, uid, modo, msg_count in usuarios_recientes:
            emoji = "🔥" if modo == "humano" else "🤖"
            stats += f"{emoji} {nombre} ({uid}): {msg_count} msgs\n"

        await update.message.reply_text(stats)

    except Exception as e:
        await update.message.reply_text(f"❌ Error obteniendo estadísticas: {e}")

# --- ARRANQUE ---
def main():
    iniciar_db()
    app = Application.builder().token(TOKEN_TELEGRAM).build()

    # --- ORDEN DE LOS HANDLERS (CRÍTICO) ---

    # 1. Comandos (Siempre van primero)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", postear_texto_grupo))
    app.add_handler(CommandHandler("cerrar", cerrar_ticket))
    app.add_handler(CommandHandler("stats", ver_estadisticas))
    app.add_handler(CommandHandler("leads", ver_leads_activos))
    app.add_handler(CommandHandler("cerrartodos", cerrar_todos_leads))
    app.add_handler(CommandHandler("historial", ver_historial_usuario))

    # 2. Multimedia y Admin (Ignoran comandos)
    app.add_handler(MessageHandler((filters.PHOTO | filters.VIDEO) & filters.ChatType.PRIVATE & filters.User(ID_ADMIN), publicar_media_admin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE & filters.User(ID_ADMIN), admin_responde_texto))

    # 3. Usuarios Generales (IA) - Siempre al final
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.User(ID_ADMIN), manejar_mensaje_usuario))

    # Cron Job (4 Horas = 14400 segundos)
    job_queue = app.job_queue
    job_queue.run_repeating(generar_post_automatico, interval=14400, first=30)

    version_texto = "PRO 💎" if VERSION_PRO else "FREE"
    print(f"🤖 Bot Paisa 4.0 Iniciado ({version_texto})")
    print(f"⏰ Horario de publicaciones: {HORA_INICIO_POST} - {HORA_FIN_POST} ({TIMEZONE})")
    print(f"✨ Features PRO: {'Activadas' if VERSION_PRO else 'Desactivadas'}")
    print("="*50)
    app.run_polling()

if __name__ == '__main__':
    main()