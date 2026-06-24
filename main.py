import logging
import sqlite3
import os
import random
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pytz
import sys

# ================= FIX UTF-8 PARA WINDOWS + PM2 =================
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
# ================================================================

# ================= CONFIGURACIÓN SEGURA =================
load_dotenv()

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")

HORA_INICIO_POST = os.getenv("HORA_INICIO_POST", "09:00")
HORA_FIN_POST = os.getenv("HORA_FIN_POST", "22:00")
TIMEZONE = os.getenv("TIMEZONE", "America/Mexico_City")

try:
    ID_TU_GRUPO = int(os.getenv("ID_TU_GRUPO"))
    ID_ADMIN = int(os.getenv("ID_ADMIN"))
except TypeError:
    print("❌ ERROR: Revisa tu archivo .env. Los IDs deben ser números.")
    exit()

if not TOKEN_TELEGRAM:
    print("❌ ERROR: Falta TOKEN_TELEGRAM en el archivo .env")
    exit()
# ========================================================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SEPARADOR = "━━━━━━━━━━━━━━━━━━"

# --- MENSAJES PREDEFINIDOS PARA POSTS AUTOMÁTICOS ---
MENSAJES_AUTO_POST = [
    "Ayyy es que hoy ando de un ánimo... mejor escríbeme y te cuento 🙈",
    "Aquí aburridita pensando en quién se anima a hablarme un ratico 🥺",
    "No sé ustedes pero yo ya quiero que sea de noche 😏",
    "Me dijeron que soy mala para responder rápido... vengan y compruébenlo 😌",
    "Hay cosas que no subo por acá, esas se las muestro en privado 🤭",
    "Tengo un chisme buenísimo pero solo lo cuento por DM jajaja",
    "¿Por qué será que el día se me hace más corto cuando hablo con ustedes? 💕",
    "Honestamente extrañaba molestarlos por aquí 🙃",
    "Si te quedaste con ganas de hablarme ayer... pues aquí sigo 👀",
    "Antojada de un café y de una buena conversación, ¿quién se ofrece? ☕",
    "Hoy amanecí cariñosa, aprovechen antes de que se me pase 😂",
    "Vení que te tengo paciencia... y un par de sorpresas 😉",
]

# --- MENSAJES DE REENGANCHE PARA LEADS FRÍOS ---
HORAS_LEAD_FRIO = 6
MENSAJES_SEGUIMIENTO = [
    "Oye {nombre}, ¿te quedaste pensándolo? 👀 Aquí sigo cuando quieras 💕",
    "{nombre} no me dejes en visto pues 🥺 ¿en qué quedamos?",
    "¿Todo bien {nombre}? Me dejaste picada con la conversación 🙈",
    "Hey {nombre}, pasé a saludarte... no creas que me olvidé de ti 😏",
    "{nombre} mor, ¿seguimos donde nos quedamos o te dio penita? 😂",
    "Ando por aquí {nombre}, por si te animas a retomar 😌",
]

# --- BASE DE DATOS LOCAL ---
def iniciar_db():
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (user_id INTEGER PRIMARY KEY, modo TEXT, nombre TEXT, thread_msg_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mensajes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, texto TEXT, fecha TEXT, tipo TEXT)''')
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN thread_msg_id INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN seguimiento_enviado INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def guardar_mensaje(user_id, texto, tipo):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    texto_guardar = texto if texto else "[MEDIA]"
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
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("SELECT thread_msg_id FROM usuarios WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res and res[0] else None

def marcar_seguimiento_enviado(user_id):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("UPDATE usuarios SET seguimiento_enviado=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def resetear_seguimiento(user_id):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("UPDATE usuarios SET seguimiento_enviado=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_modo_usuario(user_id):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("SELECT modo FROM usuarios WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "nuevo"

def get_nombre_usuario(user_id):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("SELECT nombre FROM usuarios WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res and res[0] else None

def obtener_historial_usuario(user_id, limite=20):
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

    historial_formateado = "📜 HISTORIAL\n" + SEPARADOR + "\n\n"
    for texto, fecha, tipo in reversed(mensajes):
        emoji = "👤" if tipo == "entrada_usuario" else "💬"
        rol = "Él/Ella" if tipo == "entrada_usuario" else "Tú"
        historial_formateado += f"{emoji} [{fecha}] {rol}:\n{texto}\n\n"
    historial_formateado += SEPARADOR
    return historial_formateado

def esta_en_horario_permitido():
    try:
        tz = pytz.timezone(TIMEZONE)
        ahora = datetime.now(tz)
        hora_actual = ahora.time()
        hora_inicio = datetime.strptime(HORA_INICIO_POST, "%H:%M").time()
        hora_fin = datetime.strptime(HORA_FIN_POST, "%H:%M").time()
        if hora_inicio <= hora_fin:
            return hora_inicio <= hora_actual <= hora_fin
        else:
            return hora_actual >= hora_inicio or hora_actual <= hora_fin
    except Exception as e:
        print(f"⚠️ Error verificando horario: {e}")
        return True

# ==============================================================================
#  HELPERS DE HILO / LEAD
# ==============================================================================

def detectar_tipo_media(msg):
    if msg.video: return "Video"
    if msg.photo: return "Foto"
    if msg.voice: return "Nota de voz"
    if msg.audio: return "Audio"
    return "Media"

def extraer_user_id(mensaje):
    """Busca un (user_id) en el texto o caption de un mensaje."""
    if not mensaje:
        return None
    fuente = mensaje.text or mensaje.caption or ""
    match = re.search(r'\((\d{5,})\)', fuente)
    return int(match.group(1)) if match else None

async def abrir_o_obtener_thread(user_id, nombre, context, motivo=""):
    """
    Devuelve (thread_msg_id, es_nuevo).
    Si el lead no tiene anchor, crea uno nuevo en el chat del admin.
    """
    modo = get_modo_usuario(user_id)
    thread_id = get_thread_msg_id(user_id)

    if modo == "humano" and thread_id:
        return thread_id, False

    etiqueta = "🔁 LEAD REABIERTO" if modo == "cerrado" else "🆕 NUEVO LEAD"
    header = f"{SEPARADOR}\n{etiqueta}\n👤 {nombre} ({user_id})\n{SEPARADOR}"
    if motivo:
        header += f"\n{motivo}"

    msg = await context.bot.send_message(chat_id=ID_ADMIN, text=header)
    set_modo_usuario(user_id, "humano", nombre, thread_msg_id=msg.message_id)
    return msg.message_id, True

async def enviar_historial_al_hilo(user_id, thread_id, context):
    historial = obtener_historial_usuario(user_id, limite=20)
    if not historial or len(historial) < 100:
        return
    max_length = 4000
    if len(historial) > max_length:
        chunks = [historial[i:i+max_length] for i in range(0, len(historial), max_length)]
        for i, chunk in enumerate(chunks):
            await context.bot.send_message(
                chat_id=ID_ADMIN,
                text=f"📋 Contexto ({i+1}/{len(chunks)}):\n{chunk}",
                reply_to_message_id=thread_id
            )
    else:
        await context.bot.send_message(chat_id=ID_ADMIN, text=historial, reply_to_message_id=thread_id)

# ==============================================================================
#  PUBLICACIÓN AUTOMÁTICA (MENSAJES PREDEFINIDOS)
# ==============================================================================

async def generar_post_automatico(context: ContextTypes.DEFAULT_TYPE):
    print("⏰ Ejecutando tarea automática: Publicando post...")

    if not esta_en_horario_permitido():
        tz = pytz.timezone(TIMEZONE)
        hora_actual = datetime.now(tz).strftime("%H:%M")
        print(f"⏸️ Post automático omitido. Hora actual: {hora_actual} (Horario: {HORA_INICIO_POST}-{HORA_FIN_POST})")
        return

    mensaje = random.choice(MENSAJES_AUTO_POST)

    keyboard = [[InlineKeyboardButton("🔥 Escríbeme por privado", url=f"https://t.me/{context.bot.username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(chat_id=ID_TU_GRUPO, text=mensaje, reply_markup=reply_markup)
        print(f"✅ Post publicado: {mensaje[:50]}...")
    except Exception as e:
        print(f"❌ Error en el post automático: {e}")

# ==============================================================================
#  MANEJO DE USUARIOS → ADMIN
# ==============================================================================

async def manejar_mensaje_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return

    user_id = update.effective_user.id
    texto = update.message.text
    nombre = update.effective_user.first_name

    guardar_mensaje(user_id, texto, "entrada_usuario")
    resetear_seguimiento(user_id)

    thread_id, es_nuevo = await abrir_o_obtener_thread(user_id, nombre, context)

    await context.bot.send_message(
        chat_id=ID_ADMIN,
        text=f"👤 {nombre} ({user_id}):\n{texto}",
        reply_to_message_id=thread_id
    )

    if es_nuevo:
        await enviar_historial_al_hilo(user_id, thread_id, context)
        await update.message.reply_text(
            f"¡Quiubo {nombre} mor! 💅 Ya te leo, te respondo en un momentico 🔥"
        )

async def usuario_envia_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reenvía fotos/videos/audios/notas de voz del usuario al hilo del admin."""
    if update.message.chat.type != "private":
        return

    user_id = update.effective_user.id
    nombre = update.effective_user.first_name
    tipo = detectar_tipo_media(update.message)
    caption_original = update.message.caption or ""

    guardar_mensaje(user_id, f"[{tipo.upper()}]" + (f" {caption_original}" if caption_original else ""), "entrada_usuario")
    resetear_seguimiento(user_id)

    thread_id, es_nuevo = await abrir_o_obtener_thread(user_id, nombre, context)

    # Header con el ID para que el admin pueda hacer reply fácil
    header = f"📎 {nombre} ({user_id}) envió {tipo}:"
    if caption_original:
        header += f"\n💬 {caption_original}"

    await context.bot.send_message(chat_id=ID_ADMIN, text=header, reply_to_message_id=thread_id)
    # Reenvío real del media, también como reply al hilo
    await context.bot.copy_message(
        chat_id=ID_ADMIN,
        from_chat_id=user_id,
        message_id=update.message.message_id,
        reply_to_message_id=thread_id
    )

    if es_nuevo:
        await enviar_historial_al_hilo(user_id, thread_id, context)
        await update.message.reply_text(f"¡Ya me llegó mor! 🔥 Ahorita te contesto 💋")

# ==============================================================================
#  FUNCIONES DE ADMINISTRADOR
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nombre = user.first_name

    thread_id, es_nuevo = await abrir_o_obtener_thread(user.id, nombre, context, motivo="(usuario envió /start)")

    if es_nuevo:
        await enviar_historial_al_hilo(user.id, thread_id, context)

    await update.message.reply_text(
        f"¡Hola {nombre} bebé! 💋\n\nEscríbeme lo que quieras por aquí y te contesto personalmente 🔥"
    )

async def admin_responde_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    id_usuario_destino = extraer_user_id(update.message.reply_to_message)
    if not id_usuario_destino:
        await update.message.reply_text("⚠️ No encontré el ID. Responde a un mensaje del bot que tenga el ID entre paréntesis.")
        return

    try:
        await context.bot.send_message(chat_id=id_usuario_destino, text=update.message.text)

        thread_id = get_thread_msg_id(id_usuario_destino)
        await context.bot.send_message(
            chat_id=ID_ADMIN,
            text=f"✅ Tú → ({id_usuario_destino}):\n{update.message.text}",
            reply_to_message_id=thread_id
        )
        guardar_mensaje(id_usuario_destino, update.message.text, "salida_humano")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al enviar: {e}")

async def publicar_media_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Si el admin hace REPLY a un mensaje con ID → envía el media solo a ese lead.
    Si NO es reply → publica al grupo con botón de CTA.
    """
    tipo = detectar_tipo_media(update.message)
    caption_admin = update.message.caption or ""

    # Caso 1: admin respondiendo a un lead → enviar al lead solamente
    id_destino = extraer_user_id(update.message.reply_to_message) if update.message.reply_to_message else None
    if id_destino:
        try:
            await context.bot.copy_message(
                chat_id=id_destino,
                from_chat_id=ID_ADMIN,
                message_id=update.message.message_id,
                caption=caption_admin
            )
            thread_id = get_thread_msg_id(id_destino)
            confirmacion = f"✅ Tú → ({id_destino}) enviaste {tipo}"
            if caption_admin:
                confirmacion += f"\n💬 {caption_admin}"
            await context.bot.send_message(
                chat_id=ID_ADMIN,
                text=confirmacion,
                reply_to_message_id=thread_id
            )
            guardar_mensaje(id_destino, f"[{tipo.upper()}]" + (f" {caption_admin}" if caption_admin else ""), "salida_humano")
        except Exception as e:
            await update.message.reply_text(f"❌ Error enviando al lead: {e}")
        return

    # Caso 2: publicación al grupo
    keyboard = [[InlineKeyboardButton("🔥 Escribeme al privado mor", url=f"https://t.me/{context.bot.username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.copy_message(
            chat_id=ID_TU_GRUPO,
            from_chat_id=ID_ADMIN,
            message_id=update.message.message_id,
            caption=caption_admin,
            reply_markup=reply_markup
        )
        await update.message.reply_text(f"✅ {tipo} publicado/a en el grupo.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cerrar_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ID_ADMIN:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Responde (Reply) a un mensaje del lead para cerrar su ticket.\nO usa /cerrarid <user_id>")
        return

    id_usuario = extraer_user_id(update.message.reply_to_message)
    if not id_usuario:
        await update.message.reply_text("❌ No encontré el ID en el mensaje al que respondiste.")
        return

    set_modo_usuario(id_usuario, "cerrado", get_nombre_usuario(id_usuario) or "Usuario")
    await update.message.reply_text(f"✅ Ticket cerrado para ({id_usuario}).")
    try:
        await context.bot.send_message(chat_id=id_usuario, text="Cualquier cosa no dudes en avisarme mor. 👋")
    except Exception:
        pass

async def cerrar_por_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cierra un ticket por ID sin necesidad de reply."""
    if update.effective_user.id != ID_ADMIN:
        return
    if not context.args:
        await update.message.reply_text("❌ Uso: /cerrarid <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return

    set_modo_usuario(user_id, "cerrado", get_nombre_usuario(user_id) or "Usuario")
    await update.message.reply_text(f"✅ Ticket cerrado para ({user_id}).")
    try:
        await context.bot.send_message(chat_id=user_id, text="Cualquier cosa no dudes en avisarme mor. 👋")
    except Exception:
        pass

async def abrir_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trae al tope del chat el hilo de un lead (útil para no perderse)."""
    if update.effective_user.id != ID_ADMIN:
        return
    if not context.args:
        await update.message.reply_text("❌ Uso: /abrir <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return

    nombre = get_nombre_usuario(user_id)
    if not nombre:
        await update.message.reply_text(f"⚠️ No hay registro del usuario {user_id}.")
        return

    # Forzar creación de nuevo anchor (aunque ya exista)
    set_modo_usuario(user_id, "cerrado", nombre)  # lo marca como cerrado para que el helper cree nuevo anchor
    thread_id, _ = await abrir_o_obtener_thread(user_id, nombre, context, motivo="(reabierto manualmente)")
    await enviar_historial_al_hilo(user_id, thread_id, context)
    await update.message.reply_text(f"✅ Hilo de {nombre} ({user_id}) reabierto arriba ⬆️")

async def postear_texto_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ID_ADMIN:
        return

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
    if update.effective_user.id != ID_ADMIN:
        return

    if not context.args:
        await update.message.reply_text("❌ Uso: /historial <user_id>")
        return

    try:
        user_id = int(context.args[0])
        historial = obtener_historial_usuario(user_id, limite=30)

        if len(historial) > 100:
            max_length = 4000
            if len(historial) > max_length:
                chunks = [historial[i:i+max_length] for i in range(0, len(historial), max_length)]
                for i, chunk in enumerate(chunks):
                    await update.message.reply_text(f"📋 Parte {i+1}/{len(chunks)}:\n{chunk}")
            else:
                await update.message.reply_text(historial)
        else:
            await update.message.reply_text(f"⚠️ No hay historial suficiente para ({user_id})")

    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número válido")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def ver_leads_activos(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        texto = f"🔥 LEADS ACTIVOS ({len(leads)})\n{SEPARADOR}\n\n"
        for i, (nombre, uid, ultimo_msg) in enumerate(leads, 1):
            fecha = ultimo_msg if ultimo_msg else "Sin mensajes"
            texto += f"{i}. 👤 {nombre} ({uid})\n   📅 {fecha}\n\n"

        texto += SEPARADOR + "\n"
        texto += "💡 /abrir <id> → trae el hilo arriba\n"
        texto += "💡 /cerrarid <id> → cierra sin reply\n"
        texto += "💡 /cerrartodos → cierra todos"
        await update.message.reply_text(texto)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cerrar_todos_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        c.execute("UPDATE usuarios SET modo='cerrado' WHERE modo='humano'")
        conn.commit()
        conn.close()

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
    if update.effective_user.id != ID_ADMIN:
        return

    try:
        conn = sqlite3.connect('historial_chat.db')
        c = conn.cursor()

        c.execute("SELECT COUNT(DISTINCT user_id) FROM usuarios")
        total_usuarios = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM usuarios WHERE modo='humano'")
        leads_activos = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM mensajes")
        total_mensajes = c.fetchone()[0]

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

        stats = f"📊 ESTADÍSTICAS DEL BOT\n{SEPARADOR}\n\n"
        stats += f"👥 Total usuarios: {total_usuarios}\n"
        stats += f"🔥 Leads activos: {leads_activos}\n"
        stats += f"💬 Total mensajes: {total_mensajes}\n"
        stats += f"⏰ Horario posts: {HORA_INICIO_POST} - {HORA_FIN_POST}\n\n"
        stats += f"📋 ÚLTIMOS 5 USUARIOS ACTIVOS:\n"

        for nombre, uid, modo, msg_count in usuarios_recientes:
            emoji = "🔥" if modo == "humano" else "💤"
            stats += f"{emoji} {nombre} ({uid}): {msg_count} msgs\n"

        await update.message.reply_text(stats)

    except Exception as e:
        await update.message.reply_text(f"❌ Error obteniendo estadísticas: {e}")

# ==============================================================================
#  SEGUIMIENTO AUTOMÁTICO DE LEADS FRÍOS
# ==============================================================================

async def seguimiento_leads_frios(context: ContextTypes.DEFAULT_TYPE):
    """Reengancha leads activos que el admin respondió y llevan HORAS_LEAD_FRIO
    en silencio. Envía el mensaje una sola vez (hasta que el lead vuelva a escribir)
    y solo dentro del horario permitido."""
    if not esta_en_horario_permitido():
        return

    limite = (datetime.now() - timedelta(hours=HORAS_LEAD_FRIO)).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("""
        SELECT u.user_id, u.nombre, MAX(m.fecha) AS ultima,
               (SELECT tipo FROM mensajes WHERE user_id=u.user_id ORDER BY fecha DESC LIMIT 1) AS ultimo_tipo
        FROM usuarios u
        JOIN mensajes m ON u.user_id = m.user_id
        WHERE u.modo='humano' AND COALESCE(u.seguimiento_enviado, 0) = 0
        GROUP BY u.user_id
        HAVING ultima < ? AND ultimo_tipo = 'salida_humano'
    """, (limite,))
    frios = c.fetchall()
    conn.close()

    if not frios:
        return

    print(f"🔁 Seguimiento: {len(frios)} lead(s) frío(s) detectado(s).")
    for user_id, nombre, ultima, ultimo_tipo in frios:
        mensaje = random.choice(MENSAJES_SEGUIMIENTO).format(nombre=nombre or "mor")
        try:
            await context.bot.send_message(chat_id=user_id, text=mensaje)
            guardar_mensaje(user_id, mensaje, "salida_humano")
            marcar_seguimiento_enviado(user_id)
            thread_id = get_thread_msg_id(user_id)
            await context.bot.send_message(
                chat_id=ID_ADMIN,
                text=f"🔁 Seguimiento automático → {nombre} ({user_id}):\n{mensaje}",
                reply_to_message_id=thread_id
            )
        except Exception as e:
            print(f"⚠️ Error en seguimiento a {user_id}: {e}")

async def enviar_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía un mensaje de promoción a todos los leads (activos + cerrados)."""
    if update.effective_user.id != ID_ADMIN:
        return

    mensaje = " ".join(context.args)
    if not mensaje:
        await update.message.reply_text(
            "❌ Uso: /promo <texto de la promo>\n\nEj: /promo Hoy 20% de descuento solo por las próximas 2 horas 🔥"
        )
        return

    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("SELECT user_id, nombre FROM usuarios WHERE modo IN ('humano', 'cerrado')")
    destinatarios = c.fetchall()
    conn.close()

    if not destinatarios:
        await update.message.reply_text("⚠️ No hay leads a quienes enviarles la promo.")
        return

    await update.message.reply_text(f"📤 Enviando promo a {len(destinatarios)} lead(s)...")

    enviados = 0
    errores = 0
    for user_id, nombre in destinatarios:
        try:
            await context.bot.send_message(chat_id=user_id, text=mensaje)
            guardar_mensaje(user_id, f"[PROMO] {mensaje}", "salida_humano")
            enviados += 1
        except Exception:
            errores += 1

    resumen = f"✅ Promo enviada a {enviados} lead(s)."
    if errores:
        resumen += f"\n⚠️ {errores} no la recibieron (bloquearon el bot o nunca lo iniciaron)."
    await update.message.reply_text(resumen)

# --- MENÚ DE COMANDOS ---
async def configurar_menu(app):
    """Configura el menú '/' del bot: comandos completos para el admin,
    solo /start para los usuarios normales."""
    comandos_admin = [
        BotCommand("post", "Publicar un mensaje al grupo"),
        BotCommand("promo", "Enviar una promo a todos los leads"),
        BotCommand("leads", "Ver leads activos"),
        BotCommand("stats", "Ver estadísticas del bot"),
        BotCommand("historial", "Ver historial de un usuario <id>"),
        BotCommand("abrir", "Reabrir el hilo de un lead <id>"),
        BotCommand("cerrar", "Cerrar ticket (responde al lead)"),
        BotCommand("cerrarid", "Cerrar ticket por <id>"),
        BotCommand("cerrartodos", "Cerrar todos los leads activos"),
    ]
    comandos_usuario = [
        BotCommand("start", "Iniciar conversación"),
    ]
    # Menú para todos los usuarios (mínimo)
    await app.bot.set_my_commands(comandos_usuario, scope=BotCommandScopeDefault())
    # Menú completo solo en tu chat de admin
    await app.bot.set_my_commands(comandos_admin, scope=BotCommandScopeChat(chat_id=ID_ADMIN))
    print("✅ Menú de comandos configurado.")

# --- ARRANQUE ---
def main():
    iniciar_db()
    app = Application.builder().token(TOKEN_TELEGRAM).post_init(configurar_menu).build()

    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", postear_texto_grupo))
    app.add_handler(CommandHandler("promo", enviar_promo))
    app.add_handler(CommandHandler("cerrar", cerrar_ticket))
    app.add_handler(CommandHandler("cerrarid", cerrar_por_id))
    app.add_handler(CommandHandler("cerrartodos", cerrar_todos_leads))
    app.add_handler(CommandHandler("abrir", abrir_conversacion))
    app.add_handler(CommandHandler("leads", ver_leads_activos))
    app.add_handler(CommandHandler("stats", ver_estadisticas))
    app.add_handler(CommandHandler("historial", ver_historial_usuario))

    # Admin: media (reply a lead = enviar; sin reply = publicar al grupo)
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO) & filters.ChatType.PRIVATE & filters.User(ID_ADMIN),
        publicar_media_admin
    ))
    # Admin: texto (responder a lead)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE & filters.User(ID_ADMIN),
        admin_responde_texto
    ))

    # Usuario: texto
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.User(ID_ADMIN),
        manejar_mensaje_usuario
    ))
    # Usuario: media (foto/video/voz/audio) → reenvía al hilo del admin
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO) & filters.ChatType.PRIVATE & ~filters.User(ID_ADMIN),
        usuario_envia_media
    ))

    job_queue = app.job_queue
    job_queue.run_repeating(generar_post_automatico, interval=21600, first=30)
    job_queue.run_repeating(seguimiento_leads_frios, interval=3600, first=60)

    print("🤖 Bot Paisa 4.0 Iniciado (MODO PRIVADO DIRECTO)")
    print(f"⏰ Horario de publicaciones: {HORA_INICIO_POST} - {HORA_FIN_POST} ({TIMEZONE})")
    print(SEPARADOR)
    app.run_polling()

if __name__ == '__main__':
    main()
