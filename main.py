import logging
import sqlite3
import os
import asyncio
import re
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# ================= CONFIGURACIÓN SEGURA =================
load_dotenv() # Carga las claves del archivo .env

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

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

# ==============================================================================
#  LOGICA DE PUBLICACIÓN AUTOMÁTICA
# ==============================================================================

async def generar_post_automatico(context: ContextTypes.DEFAULT_TYPE):
    """Se ejecuta automáticamente según el tiempo programado"""
    print("⏰ Ejecutando tarea automática: Generando post...")
    
    prompt = "Eres una mujer influencer colombiana (de medallo) de 27 años radicando en la CDMX. Genera un mensaje corto, picarón y enganchador para tu audiencia en Telegram. El objetivo es que te escriban por privado. No uses saludos como 'hola chicos', ve directo al grano. Usa emojis."
    
    try:
        response = model.generate_content(prompt)
        mensaje_ia = response.text
        
        mensaje_final = f"\n\n{mensaje_ia}"
        
        keyboard = [[InlineKeyboardButton("🔥 Escríbeme por privado", url=f"https://t.me/{context.bot.username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id=ID_TU_GRUPO, text=mensaje_final, reply_markup=reply_markup)
        
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
            await context.bot.send_message(chat_id=ID_ADMIN, text=f"🚨 **LEAD CALIENTE (IA)** 🚨\nUsuario: {nombre} ({user_id})\nIntención Detectada: Negocios\nDijo: {texto}")
        else:
            # MODO CHAT (Personalidad Paisa REFORZADA con Few-Shot)
            prompt_respuesta = f"""
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
            
            AHORA RESPONDE AL USUARIO:
            User: "{texto}"
            Tú:
            """
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
    await update.message.reply_text(f"¡Hola {user.first_name}! ¿Qué se te antoja hacer hoy mor?")

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

# --- ARRANQUE ---
def main():
    iniciar_db()
    app = Application.builder().token(TOKEN_TELEGRAM).build()

    # --- ORDEN DE LOS HANDLERS (CRÍTICO) ---
    
    # 1. Comandos (Siempre van primero)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", postear_texto_grupo))
    app.add_handler(CommandHandler("cerrar", cerrar_ticket))

    # 2. Multimedia y Admin (Ignoran comandos)
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE & filters.User(ID_ADMIN), publicar_foto_admin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE & filters.User(ID_ADMIN), admin_responde_texto))

    # 3. Usuarios Generales (IA) - Siempre al final
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.User(ID_ADMIN), manejar_mensaje_usuario))

    # Cron Job (4 Horas = 14400 segundos)
    job_queue = app.job_queue
    job_queue.run_repeating(generar_post_automatico, interval=14400, first=30)
    
    print("🤖 Bot Paisa 3.1 Iniciado (Personalidad Fuerte)...")
    app.run_polling()

if __name__ == '__main__':
    main()