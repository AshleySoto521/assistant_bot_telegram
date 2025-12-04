# 🤖 Telegram Influencer AI Bot (Smart Handoff 3.0)

Este es un bot de Telegram avanzado diseñado para influencers y marcas personales. A diferencia de los bots tradicionales, este utiliza **Inteligencia Artificial (Gemini 2.5 Flash)** para "leer la mente" del usuario: distingue automáticamente entre una charla casual y una oportunidad de negocio.

El sistema opera bajo la arquitectura **"Human-in-the-Loop"**: La IA entretiene a la audiencia, pero cuando detecta dinero (intención de compra), le pasa el control al humano.

**Coste de Operación:** 0€ (Usando Free Tier de Google y Hosting Local).

## ✨ Características Principales

* **🧠 Cerebro Clasificador (Smart Filter):** Ya no usa listas de palabras tontas. La IA analiza el contexto de cada mensaje.
    * *Ejemplo:* "Tu ropa es linda" -> **IA Responde** (Chat).
    * *Ejemplo:* "Quiero comprar esa ropa" -> **Te avisa a ti** (Venta).
* **🎟️ Sistema de Tickets (/cerrar):** Cuando terminas de atender a un cliente humano, usas un comando para que la IA vuelva a tomar el control de ese usuario automáticamente.
* **📢 Megáfono (/post):** Comando administrativo para enviar anuncios de texto directamente al canal/grupo desde el chat privado del bot.
* **📸 Modo Espejo (Fotos):** Si envías una foto al bot por privado, él la "repostea" en el grupo añadiendo botones de contacto (Call to Action).
* **⏰ Publicador Automático:** Genera temas de conversación picantes/interesantes mediante IA y los publica en el grupo cada 4 horas para mantener el engagement.
* **📂 Base de Datos Local:** Gestión de historial y estados de usuario mediante SQLite (100% privado y sin servidores).

## 🛠️ Requisitos Técnicos

* Python 3.10 o superior.
* Una cuenta de Google AI Studio (API Key de Gemini).
* Un Bot de Telegram (creado con @BotFather).

## 📦 Instalación y Dependencias

1.  **Clonar/Descargar el proyecto** en tu equipo local.
2.  **Instalar dependencias:**
    Abre tu terminal en la carpeta del proyecto y ejecuta:
    ```bash
    pip install -r requirements.txt
    ```
    *Contenido del requirements.txt:*
    ```text
    python-telegram-bot[job-queue]
    google-generativeai
    python-dotenv
    ```

## ⚙️ Configuración (.env)

El proyecto utiliza un archivo de seguridad. Crea un archivo llamado `.env` en la raíz del proyecto y configura tus claves:

```env
TOKEN_TELEGRAM=tu_token_aqui
GOOGLE_API_KEY=tu_api_key_de_google
ID_TU_GRUPO=-100xxxxxxxxxx  (Recuerda incluir el signo menos)
ID_ADMIN=123456789          (Tu ID personal para tener permisos)