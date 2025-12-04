from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- PEGA TU TOKEN AQUÍ PARA ESTA PRUEBA ---
TOKEN = "TU_TOKEN_AQUI"

async def chivato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("\n" + "="*30)
    print("🕵️  NUEVO MENSAJE CAPTURADO")
    print(f"👤 Tu ID personal (ID_ADMIN): {update.effective_user.id}")
    
    # Si el mensaje viene de un grupo, el ID del chat será negativo
    if update.effective_chat.type in ["group", "supergroup"]:
        print(f"📢 ID del Grupo (ID_TU_GRUPO): {update.effective_chat.id}")
    else:
        print(f"💬 ID del Chat Privado: {update.effective_chat.id}")
        
    print("="*30 + "\n")

def main():
    app = Application.builder().token(TOKEN).build()
    # Escuchar TODO: Texto, fotos, unirse a grupos...
    app.add_handler(MessageHandler(filters.ALL, chivato))
    
    print("🕵️  Detector iniciado. Escribe al bot o mételo al grupo...")
    app.run_polling()

if __name__ == '__main__':
    main()