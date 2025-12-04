import logging
import sqlite3
import os
import asyncio
import re
from dotenv import load_dotenv
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import pytz

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

genai.configure(api_key=GOOGLE_API_KEY)
# Usamos el modelo más rápido que solicitaste, o usa 'gemini-1.5-flash' para evitar límites del plan gratuito.
model = genai.GenerativeModel('gemini-2.5-flash')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- BASE DE DATOS LOCAL ---
def iniciar_db():
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (user_id INTEGER PRIMARY KEY, modo TEXT, nombre TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mensajes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, texto TEXT, fecha TEXT, tipo TEXT)''')
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

def set_modo_usuario(user_id, modo, nombre="Usuario"):
    conn = sqlite3.connect('historial_chat.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO usuarios (user_id, modo, nombre) VALUES (?, ?, ?)", (user_id, modo, nombre))
    conn.commit()
    conn.close()

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

    prompt_base = "Eres una mujer influencer colombiana (de medallo) de 27 años radicando en la CDMX. Genera un mensaje corto, picarón y enganchador para tu audiencia en Telegram. El objetivo es que te escriban por privado. No uses saludos como 'hola chicos', ve directo al grano. Usa emojis."

    # Feature PRO: Posts más personalizados y variados
    if VERSION_PRO:
        prompt = prompt_base + "\n\nVARIANTE PRO: Alterna entre estos estilos: 1) Pregunta provocativa, 2) Historia corta intrigante, 3) Consejo atrevido, 4) Confesión picante. Elige uno al azar y hazlo único."
    else:
        prompt = prompt_base

    try:
        response = model.generate_content(prompt)
        mensaje_ia = response.text

        mensaje_final = f"\n\n{mensaje_ia}"

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
    
    # Si ya está en modo humano, te reenvía todo directo
    modo = get_modo_usuario(user_id)
    if modo == "humano":
        await context.bot.send_message(chat_id=ID_ADMIN, text=f"📩 Mensaje de {nombre} ({user_id}):\n\n{texto}")
        return

    # --- CLASIFICACIÓN CON IA ---
    try:
        prompt_clasificacion = f"""
        Actúa como un filtro de seguridad. Analiza el mensaje: "{texto}".
        - Si quiere comprar, saber precios, contratar, colaborar: Responde VENTA
        - Si es un saludo, broma, charla casual: Responde CHAT
        Responde solo una palabra.
        """
        
        clasificacion = model.generate_content(prompt_clasificacion).text.strip().upper()
        print(f"🧠 IA Analiza: '{texto}' -> {clasificacion}")

        if "VENTA" in clasificacion:
            # ACTIVAR MODO HUMANO
            set_modo_usuario(user_id, "humano", nombre)
            await update.message.reply_text("¡Uff, mi amor! 👀 Te paso toda la info para tratarte como te mereces:")

            # Preparar notificación para el admin
            notificacion = f"🚨 **LEAD CALIENTE (IA)** 🚨\nUsuario: {nombre} ({user_id})\nIntención Detectada: Negocios\nMensaje que activó lead: {texto}"

            # Enviar notificación inicial
            await context.bot.send_message(chat_id=ID_ADMIN, text=notificacion)

            # Enviar historial de conversación para dar contexto
            historial = obtener_historial_usuario(user_id, limite=20)
            if historial and len(historial) > 100:  # Solo si hay historial significativo
                # Dividir historial en chunks si es muy largo (límite de Telegram: 4096 caracteres)
                max_length = 4000
                if len(historial) > max_length:
                    chunks = [historial[i:i+max_length] for i in range(0, len(historial), max_length)]
                    for i, chunk in enumerate(chunks):
                        await context.bot.send_message(chat_id=ID_ADMIN, text=f"📋 Contexto (parte {i+1}/{len(chunks)}):\n{chunk}")
                else:
                    await context.bot.send_message(chat_id=ID_ADMIN, text=historial)
        else:
            # MODO CHAT (Personalidad Paisa REFORZADA con Few-Shot)
            prompt_base = """
            Instrucciones de Personalidad:
            Eres "Fer Ruiz", una influencer colombiana (paisa) de 27 años viviendo en CDMX.
            - Tu tono es: Coqueta, picaróna, relajada y muy "de barrio" pero fresa.
            - Palabras obligatorias: Mor, bebé, parce, nea, qué más pues, obvio bobis.
            - NUNCA respondas como robot ("Soy una IA", "En qué puedo ayudarte").
            - Si te saludan, no digas "Hola". Di algo como: "Quiubo mor", "Hola bebé".
            - Usa emojis en cada mensaje: 🔥, 😈, 👀, 💅.
            - Tus respuestas deben ser CORTAS (máximo 2 líneas).

            Ejemplos de cómo respondes (Copia este estilo):
            User: ¿Qué haces?
            Tú: Aquí pensando en cuándo me vas a invitar a salir mor 💅

            User: Eres un robot?
            Tú: Obvio no bobis, soy tu tormento 😈

            User: Te ves bien
            Tú: Yo sé que te encanto parce, no lo niegues 💅🔥
            """

            # Feature PRO: Memoria conversacional (considera mensajes anteriores)
            if VERSION_PRO:
                # Obtener últimos 5 mensajes para contexto
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

                prompt_respuesta = prompt_base + contexto_previo + f"\n\nAHORA RESPONDE AL USUARIO (considera el contexto):\nUser: \"{texto}\"\nTú:"
            else:
                prompt_respuesta = prompt_base + f"\n\nAHORA RESPONDE AL USUARIO:\nUser: \"{texto}\"\nTú:"

            response = model.generate_content(prompt_respuesta)
            await update.message.reply_text(response.text)
            guardar_mensaje(user_id, response.text, "salida_ia")

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

    texto_original = update.message.reply_to_message.text or ""
    # Busca ID en formato (123456)
    match = re.search(r'\((\d{5,})\)', texto_original)

    if match:
        try:
            id_usuario_destino = int(match.group(1))
            await context.bot.send_message(chat_id=id_usuario_destino, text=update.message.text)
            await update.message.reply_text(f"✅ Enviado al usuario {id_usuario_destino}.")
            guardar_mensaje(id_usuario_destino, update.message.text, "salida_humano")
        except Exception as e:
            await update.message.reply_text(f"❌ Error al enviar: {e}")
    else:
        await update.message.reply_text("⚠️ No encontré el ID. Asegúrate de responder a un mensaje del bot que tenga el ID entre paréntesis.")

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

async def publicar_foto_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_foto = update.message.caption if update.message.caption else ""
    keyboard = [[InlineKeyboardButton("🔥 Escribeme al privado mor", url=f"https://t.me/{context.bot.username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.copy_message(chat_id=ID_TU_GRUPO, from_chat_id=ID_ADMIN, message_id=update.message.message_id, caption=texto_foto, reply_markup=reply_markup)
        await update.message.reply_text("✅ Foto publicada.")
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
    app.add_handler(CommandHandler("historial", ver_historial_usuario))

    # 2. Multimedia y Admin (Ignoran comandos)
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE & filters.User(ID_ADMIN), publicar_foto_admin))
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